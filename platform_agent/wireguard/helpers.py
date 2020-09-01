import datetime
import os
import ipaddress

from icmplib import multiping
from pyroute2 import NetlinkError

from platform_agent.cmd.lsmod import module_loaded, is_tool
from platform_agent.cmd.wg_info import WireGuardRead
from platform_agent.network.iface_watcher import read_tmp_file

WG_NAME_SUBSTRINGS = ['p2p_', 'mesh_', 'gw_']


def get_peer_info(ifname, wg, kind=None):
    results = {}
    if kind == 'wireguard' or os.environ.get("NOIA_WIREGUARD"):
        try:
            ss = wg.info(ifname)
        except NetlinkError as e:
            return results
        wg_info = dict(ss[0]['attrs'])
        peers = wg_info.get('WGDEVICE_A_PEERS', [])
        for peer in peers:
            peer = dict(peer['attrs'])
            try:
                results[peer['WGPEER_A_PUBLIC_KEY'].decode('utf-8')] = [allowed_ip['addr'] for allowed_ip in
                                                                        peer['WGPEER_A_ALLOWEDIPS']]
            except KeyError:
                results[peer['WGPEER_A_PUBLIC_KEY'].decode('utf-8')] = []
    else:
        wg = WireGuardRead()
        iface = wg.wg_info(ifname)[0]
        for peer in iface['peers']:
            results[peer['peer']] = peer['allowed_ips']
    return results


def get_peer_info_all(ifname, wg, kind=None):
    results = []
    if kind == 'wireguard' or os.environ.get("NOIA_WIREGUARD"):
        try:
            ss = wg.info(ifname)
        except NetlinkError as e:
            return results
        wg_info = dict(ss[0]['attrs'])
        peers = wg_info.get('WGDEVICE_A_PEERS', [])
        for peer in peers:
            try:
                peer_dict = dict(peer['attrs'])
                results.append({
                    "public_key": peer_dict['WGPEER_A_PUBLIC_KEY'].decode('utf-8'),
                    "allowed_ips": [allowed_ip['addr'] for allowed_ip in peer_dict['WGPEER_A_ALLOWEDIPS']],
                    "last_handshake": datetime.datetime.strptime(
                        peer_dict['WGPEER_A_LAST_HANDSHAKE_TIME']['latest handshake'],
                        "%a %b %d %H:%M:%S %Y").isoformat(),
                    "keep_alive_interval": peer_dict['WGPEER_A_PERSISTENT_KEEPALIVE_INTERVAL'],
                    "rx_bytes": peer_dict['WGPEER_A_RX_BYTES'],
                    "tx_bytes": peer_dict['WGPEER_A_TX_BYTES'],
                })
            except KeyError:
                continue

    else:
        wg = WireGuardRead()
        iface = wg.wg_info(ifname)[0]
        for peer in iface['peers']:
            try:
                results.append({
                    "public_key": peer['peer'],
                    "last_handshake": datetime.datetime.now().isoformat() if peer['latest_handshake'] else None,
                    "keep_alive_interval": peer['persistent_keepalive'],
                    "allowed_ips": peer['allowed_ips'],
                })
            except KeyError:
                continue
    return results


def get_peer_ips(ifname, wg, internal_ip, kind=None):
    peers_info = []
    peers_internal_ip = []
    peers = get_peer_info_all(ifname, wg, kind=kind)
    for peer in peers:
        peer_internal_ip = next(
            (
                ip for ip in peer['allowed_ips']
                if
                ipaddress.ip_address(ip.split('/')[0]) in ipaddress.ip_network(f"{internal_ip.split('/')[0]}/24",
                                                                               False)
            ),
            None
        )
        if not peer_internal_ip:
            continue
        peer.update({'internal_ip': peer_internal_ip.split('/')[0]})
        peers_info.append(peer)
        peers_internal_ip.append(peer_internal_ip.split('/')[0])
    return peers_info, peers_internal_ip


def check_if_wireguard_installled():
    return module_loaded('wireguard') or is_tool('wireguard-go')


def ping_internal_ips(ips, count=4, interval=0.5):
    result = {}
    ping_res = multiping(ips, count=count, interval=interval)
    for res in ping_res:
        result[res.address] = {
            "latency_ms": res.avg_rtt if res.is_alive else 10000,
            "packet_loss": res.packet_loss if res.is_alive else 1
        }
    return result


def merged_peer_info(wg):
    result = []
    peers_ips = []
    interfaces = read_tmp_file(file_type='iface_info')
    res = {k: v for k, v in interfaces.items() if
           any(substring in k for substring in WG_NAME_SUBSTRINGS)}
    for ifname in res.keys():
        if not res[ifname].get('internal_ip'):
            continue
        peer_info, peers_internal_ips = get_peer_ips(ifname, wg, res[ifname]['internal_ip'], kind=res[ifname]['kind'])
        peers_ips += peers_internal_ips
        result.append(
            {
                "iface": ifname,
                "peers": peer_info
            }
        )
    pings = ping_internal_ips(peers_ips, count=10, interval=0.3)
    for iface in result:
        for peer in iface['peers']:
            peer.update(pings[peer['internal_ip']])
    return result
