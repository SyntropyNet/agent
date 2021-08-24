import threading
import time
import logging
import pyroute2
import json

from platform_agent.lib.file_helper import check_if_file_exist, read_tmp_file
from pyroute2 import WireGuard

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.cmd.wg_info import WireGuardRead
from platform_agent.files.tmp_files import get_peer_metadata
from platform_agent.routes import Routes
from platform_agent.lib.ctime import now

logger = logging.getLogger()


def get_interface_internal_ip(ifname):
    with pyroute2.IPDB() as ipdb:
        internal_ip = f"{ipdb.interfaces[ifname]['ipaddr'][0]['address']}"
        return internal_ip


def generate_routing_info(peers_info):
    routing_info = {}
    for ifname, peers in peers_info.items():
        for peer_public_key, peer_data in peers_info[ifname]['peers'].items():
            if not len(peer_data['allowed_ips']) > 1:
                continue
            for allowed_ip in peer_data['allowed_ips'][:1]:
                if not routing_info.get(allowed_ip):
                    routing_info[allowed_ip] = {}
                routing_info[allowed_ip].update({ifname: peer_data})
    return routing_info


def get_fastest_routes():
    result = {}
    if check_if_file_exist("peers_info"):
        peers_info = read_tmp_file("peers_info")
        routing_info = generate_routing_info(peers_info)
    else:
        routing_info = {}

    for dest, routes in routing_info.items():
        best_route = None
        best_ping = 9999
        best_packet_loss = 1
        for iface, data in routes.items():
            if data['latency_ms'] and data['latency_ms'] < best_ping and data['packet_loss'] <= best_packet_loss:
                best_route = {'iface': iface, 'gw': data['internal_ip'], 'metadata': data.get('metadata'),
                              "public_key": data.get('public_key')}
                best_ping = data['latency_ms']
        result[dest] = best_route
    return result


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
            new_routes = get_fastest_routes()
            peers_active = []
            for dest, best_route in new_routes.items():
                if not best_route or previous_routes.get(dest) == best_route:
                    continue
                # Do rerouting logic with best_route
                logger.info(f"[REROUTING] Rerouting {dest} via {best_route}",
                            extra={'metadata': best_route.get('metadata')})
                peer_metadata = get_peer_metadata(public_key=best_route.get('public_key'))
                peers_active.append({"connection_id": peer_metadata.get("connection_id"), "timestamp": now()})
                try:
                    self.routes.ip_route_replace(
                        ifname=best_route['iface'], ip_list=[dest],
                        gw_ipv4=get_interface_internal_ip(best_route['iface'])
                    )
                except KeyError:  # catch if interface was deleted while executing this code
                    continue
            if peers_active:
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

    def join(self, timeout=None):
        self.stop_rerouting.set()
        super().join(timeout)
