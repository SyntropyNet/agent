import threading
import time
import logging
import pyroute2
import ipaddress
import json
import re

from pyroute2 import WireGuard

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.cmd.wg_info import WireGuardRead
from platform_agent.files.tmp_files import read_tmp_file, get_peer_metadata
from platform_agent.routes import Routes
from platform_agent.lib.ctime import now

from platform_agent.wireguard.helpers import WG_NAME_PATTERN, ping_internal_ips, get_peer_info_all, WG_SYNTROPY_INT

logger = logging.getLogger()


def get_routing_info(wg):
    routing_info = {}
    peers_internal_ips = []
    interfaces = read_tmp_file(file_type='iface_info')
    res = {k: v for k, v in interfaces.items() if re.match(WG_NAME_PATTERN, k) or k in WG_SYNTROPY_INT}
    peers = []
    for ifname in WG_SYNTROPY_INT:
        peers += get_peer_info_all(ifname, wg, kind=res[ifname]['kind'])
    for peer in peers:
        try:
            peer_internal_ip = next(
                (
                    ip for ip in peer['allowed_ips']
                    if
                    ipaddress.ip_address(ip.split('/')[0]) in ipaddress.ip_network(
                        f"{res[WG_SYNTROPY_INT[0]]['internal_ip'].split('/')[0]}/16",
                        False)
                ),
                None
            )
        except ValueError:
            continue
        if not peer_internal_ip:
            continue
        peers_internal_ips.append(peer_internal_ip.split('/')[0])
        peer['allowed_ips'].remove(peer_internal_ip)
        for allowed_ip in peer['allowed_ips']:
            if not routing_info.get(allowed_ip):
                routing_info[allowed_ip] = {'ifaces': {}}
            routing_info[allowed_ip]['ifaces'][peer['ifname']] = {
                "public_key": peer['public_key'],
                'internal_ip': peer_internal_ip,
                'metadata': "Empty"
            }
    return routing_info, peers_internal_ips


def get_interface_internal_ip(ifname):
    with pyroute2.IPDB() as ipdb:
        internal_ip = f"{ipdb.interfaces[ifname]['ipaddr'][0]['address']}"
        return internal_ip


def get_fastest_routes(wg):
    result = {}
    routing_info, peers_internal_ips = get_routing_info(wg)
    ping_results = ping_internal_ips(peers_internal_ips, icmp_id=20000)
    for dest, routes in routing_info.items():
        best_route = None
        best_ping = 9999
        for iface, data in routes['ifaces'].items():
            int_ip = data['internal_ip'].split('/')[0]
            if ping_results[int_ip]['latency_ms'] < best_ping:
                best_route = {'iface': iface, 'gw': data['internal_ip'], 'metadata': data.get('metadata'), "public_key": data.get('public_key')}
                best_ping = ping_results[int_ip]['latency_ms']
        result[dest] = best_route
    return result, ping_results


class Rerouting(threading.Thread):

    def __init__(self, client, interval=1):
        logger.debug(f"[REROUTING] Initializing")
        super().__init__()
        self.interval = interval
        self.client = client
        self.wg = WireGuard() if module_loaded("wireguard") else WireGuardRead()
        self.routes = Routes()
        self.stop_rerouting = threading.Event()
        self.daemon = True

    def run(self):
        logger.debug(f"[REROUTING] Running")
        previous_routes = {}
        while not self.stop_rerouting.is_set():
            new_routes, ping_data = get_fastest_routes(self.wg)
            peers_active = []
            for dest, best_route in new_routes.items():
                if not best_route or previous_routes.get(dest) == best_route:
                    continue
                # Do rerouting logic with best_route
                logger.debug(f"[REROUTING] Rerouting {dest} via {best_route}", extra={'metadata': best_route.get('metadata')})
                peer_metadata = get_peer_metadata(public_key=best_route.get('public_key'))
                peers_active.append({"connection_id": peer_metadata.get("connection_id"), "timestamp": str(time.time())})
                try:
                    self.routes.ip_route_replace(
                        ifname=best_route['iface'], ip_list=[dest],
                        gw_ipv4=get_interface_internal_ip(best_route['iface'])
                    )
                except KeyError:  # catch if interface was deleted while executing this code
                    continue
            self.send_active_route(peers_active)
            previous_routes = new_routes
            time.sleep(int(self.interval))

    def send_active_route(self, data):
        self.client.send_log(json.dumps({
            'id': "ID." + str(time.time()),
            'executed_at': now(),
            'type': 'IFACES_PEERS_ACTIVE_DATA',
            'data': data
        }))

    def send_latency_data(self, data):
        self.client.send_log(json.dumps({
            'id': "ID." + str(time.time()),
            'executed_at': now(),
            'type': 'PEERS_LATENCY_DATA',
            'data': data
        }))

    def join(self, timeout=None):
        self.stop_rerouting.set()
        super().join(timeout)
