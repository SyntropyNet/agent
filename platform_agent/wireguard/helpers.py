import datetime
import os
import ipaddress
import re
import psutil
import socket
from random import randint

import requests
from icmplib import multiping
from pyroute2 import NetlinkError

from platform_agent.cmd.lsmod import module_loaded, is_tool
from platform_agent.cmd.wg_info import WireGuardRead
from platform_agent.network.iface_watcher import read_tmp_file

WG_NAME_PATTERN = '[0-9]{10}(s1|s2|s3|p0)+(g|m|p)[Nn][Oo]'
WG_SYNTROPY_INT = ['SYNTROPY_PUBLIC', 'SYNTROPY_SDN1', 'SYNTROPY_SDN2', 'SYNTROPY_SDN3']


def get_connection_status(latency_ms, packet_loss):
    if packet_loss >= 1:
        res = {'status': 'OFFLINE', 'status_reason': 'Packet loss 100%'}
    elif 0.01 <= packet_loss <= 1:
        res = {'status': 'WARNING', 'status_reason': 'Packet loss higher than 1%'}
    elif latency_ms >= 1000:
        res = {'status': 'WARNING', 'status_reason': 'Latency higher than 1000ms'}
    else:
        res = {'status': 'CONNECTED'}
    res.update(
        {
            "latency_ms": latency_ms,
            "packet_loss": packet_loss,
        }
    )
    return res

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]

def get_public_ip():
    try:
        return requests.get("https://ip.syntropystack.com/").json()
    except:
        return requests.get('https://ident.me').text

def behind_nat():
    return bool(get_ip_address() != get_public_ip())

def find_free_port(SDN=False):

    if os.environ.get("SYNTROPY_PORT_RANGE"):
        try:
            ports = os.environ["SYNTROPY_PORT_RANGE"]
            ports = ports.split('-')
            ports_start = int(ports[0])
            ports_end = int(ports[1])
        except (IndexError, ValueError):
            return None
    elif SDN and behind_nat():
        return 0
    else:
        ports_start = 49152
        ports_end = 65535

    port = randint(ports_start, ports_end)
    portsinuse = []
    while True:
        conns = psutil.net_connections()
        for conn in conns:
            portsinuse.append(conn.laddr[1])
        if port in portsinuse:
            port = randint(ports_start, ports_end)
        else:
            break
    return port


def get_iface_public_key(ifname):
    wg = WireGuardRead()
    ifaces = wg.wg_info(ifname)
    if not ifaces:
        return
    iface = ifaces[0]
    return iface.get('public_key')


def get_peer_info(ifname, wg, kind=None):
    results = {}
    if kind == 'wireguard' or os.environ.get("SYNTROPY_WIREGUARD"):
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
        ifaces = wg.wg_info(ifname)
        if not ifaces:
            return results
        iface = ifaces[0]
        for peer in iface['peers']:
            results[peer['peer']] = peer['allowed_ips']
    return results


def get_peer_info_all(ifname, wg, kind=None):
    results = []
    # TODO NEED FIX pyroute2 wireguard info solution, because of missing peers when getting info.
    # if kind == 'wireguard' or os.environ.get("SYNTROPY_WIREGUARD"):
    #     try:
    #         ss = wg.info(ifname)
    #     except NetlinkError as e:
    #         return results
    #     wg_info = dict(ss[0]['attrs'])
    #     peers = wg_info.get('WGDEVICE_A_PEERS', [])
    #     for peer in peers:
    #         try:
    #             peer_dict = dict(peer['attrs'])
    #             results.append({
    #                 "public_key": peer_dict['WGPEER_A_PUBLIC_KEY'].decode('utf-8'),
    #                 "allowed_ips": [allowed_ip['addr'] for allowed_ip in peer_dict['WGPEER_A_ALLOWEDIPS']],
    #                 "last_handshake": datetime.datetime.strptime(
    #                     peer_dict['WGPEER_A_LAST_HANDSHAKE_TIME']['latest handshake'],
    #                     "%a %b %d %H:%M:%S %Y").isoformat(),
    #                 "keep_alive_interval": peer_dict['WGPEER_A_PERSISTENT_KEEPALIVE_INTERVAL'],
    #                 "rx_bytes": peer_dict['WGPEER_A_RX_BYTES'],
    #                 "tx_bytes": peer_dict['WGPEER_A_TX_BYTES'],
    #             })
    #         except KeyError:
    #             continue

    wg = WireGuardRead()
    ifaces = wg.wg_info(ifname)
    if not ifaces:
        return results
    iface = ifaces[0]
    for peer in iface['peers']:
        try:
            results.append({
                "ifname": ifname,
                "public_key": peer['peer'],
                "last_handshake": datetime.datetime.now().isoformat() if peer['latest_handshake'] else None,
                "keep_alive_interval": int(''.join(filter(str.isdigit, peer.get('persistent_keepalive', '15')))),
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
        try:
            peer_internal_ip = next(
                (
                    ip for ip in peer['allowed_ips']
                    if
                    ipaddress.ip_address(ip.split('/')[0]) in ipaddress.ip_network(f"{internal_ip.split('/')[0]}/16",
                                                                                   False)
                ),
                None
            )
        except ValueError:
            continue
        if not peer_internal_ip:
            continue
        peer.update({'internal_ip': peer_internal_ip.split('/')[0]})
        peers_info.append(peer)
        peers_internal_ip.append(peer_internal_ip.split('/')[0])
    return peers_info, peers_internal_ip


def check_if_wireguard_installled():
    return module_loaded('wireguard') or is_tool('wireguard-go')


def check_udp_connection():
    for pings in range(3):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.settimeout(1.0)
        message = b'test'
        addr = ("udp-check.syntropystack.com", 12000)
        client_socket.sendto(message, addr)
        try:
            client_socket.recvfrom(1024)
            return True
        except socket.timeout:
            return False


def ping_internal_ips(ips, count=4, interval=0.5, icmp_id=10000):
    result = {}
    ping_res = multiping(ips, count=count, interval=interval, id=icmp_id)
    for res in ping_res:
        latency_ms = res.avg_rtt if res.is_alive else 5000
        packet_loss = res.packet_loss if res.is_alive else 1
        result[res.address] = get_connection_status(latency_ms, packet_loss)
    return result


def merged_peer_info(wg):
    result = []
    peers_ips = []
    interfaces = read_tmp_file(file_type='iface_info')
    res = {k: v for k, v in interfaces.items() if re.match(WG_NAME_PATTERN, k) or k in WG_SYNTROPY_INT}
    for ifname in res.keys():
        if not res[ifname].get('internal_ip'):
            continue
        peer_info, peers_internal_ips = get_peer_ips(ifname, wg, res[ifname]['internal_ip'], kind=res[ifname]['kind'])
        peers_ips += peers_internal_ips
        iface_public_key = get_iface_public_key(ifname)
        if not iface_public_key:
            continue
        result.append(
            {
                "iface": ifname,
                "iface_public_key": iface_public_key,
                "peers": peer_info
            }
        )
    pings = ping_internal_ips(peers_ips, count=1, interval=0.3)
    for iface in result:
        for peer in iface['peers']:
            peer.update(pings[peer['internal_ip']])
    return result
