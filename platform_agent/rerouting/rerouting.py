import threading
import time
import logging
import pyroute2
import ipaddress
import json

from pyroute2 import WireGuard

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.cmd.wg_info import WireGuardRead
from platform_agent.routes import Routes
from platform_agent.lib.ctime import now

from platform_agent.wireguard.helpers import get_peer_info, WG_NAME_SUBSTRINGS, ping_internal_ips

logger = logging.getLogger()


def get_routing_info(wg):
    with pyroute2.IPDB() as ipdb:
        routing_info = {}
        peers_internal_ips = []
        res = {k: v for k, v in ipdb.by_name.items() if
               any(substring in v.get('ifname') for substring in WG_NAME_SUBSTRINGS)}
        for ifname in res.keys():
            if not res[ifname].get('ipaddr'):
                continue
            internal_ip = f"{res[ifname]['ipaddr'][0]['address']}/{res[ifname]['ipaddr'][0]['prefixlen']}"
            peers = get_peer_info(ifname, wg, kind=res[ifname]['kind'])
            for peer in peers.keys():
                peer_internal_ip = next(
                    (
                        ip for ip in peers[peer]
                        if
                    ipaddress.ip_address(ip.split('/')[0]) in ipaddress.ip_network(f"{internal_ip.split('/')[0]}/24",
                                                                                   False)
                    ),
                    None
                )
                if not peer_internal_ip:
                    continue
                peers_internal_ips.append(peer_internal_ip.split('/')[0])
                peers[peer].remove(peer_internal_ip)
                for allowed_ip in peers[peer]:
                    if not routing_info.get(allowed_ip):
                        routing_info[allowed_ip] = {'ifaces': {}}
                    routing_info[allowed_ip]['ifaces'][ifname] = peer_internal_ip
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
        for iface, internal_ip in routes['ifaces'].items():
            int_ip = internal_ip.split('/')[0]
            if ping_results[int_ip]['latency_ms'] < best_ping:
                best_route = {'iface': iface, 'gw': internal_ip}
                best_ping = ping_results[int_ip]['latency_ms']
        result[dest] = best_route
        logger.debug(f"[REROUTING] Ping results {ping_results}")
    return result, ping_results


class Rerouting(threading.Thread):

    def __init__(self, client, interval=1):
        logger.info(f"[REROUTING] Initializing")
        super().__init__()
        self.interval = interval
        self.client = client
        self.wg = WireGuard() if module_loaded("wireguard") else WireGuardRead()
        self.routes = Routes()
        self.stop_rerouting = threading.Event()
        self.daemon = True

    def run(self):
        logger.info(f"[REROUTING] Running")
        previous_routes = {}
        while not self.stop_rerouting.is_set():
            new_routes, ping_data = get_fastest_routes(self.wg)
            for dest, best_route in new_routes.items():
                if not best_route or previous_routes.get(dest) == best_route:
                    continue
                # Do rerouting logic with best_route
                logger.info(f"[REROUTING] Rerouting {dest} via {best_route}")
                try:
                    self.routes.ip_route_replace(
                        ifname=best_route['iface'], ip_list=[dest],
                        gw_ipv4=get_interface_internal_ip(best_route['iface'])
                    )
                except KeyError:  # catch if interface was deleted while executing this code
                    continue
            previous_routes = new_routes
            time.sleep(int(self.interval))

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
