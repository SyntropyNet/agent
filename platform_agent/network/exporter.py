import time
import socket
import os
import threading

from platform_agent.lib.file_helper import check_if_file_exist, read_tmp_file, format_results_for_controller
from prometheus_client import start_http_server, Metric, REGISTRY

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.cmd.wg_info import WireGuardRead
from platform_agent.files.tmp_files import get_peer_metadata
from pyroute2 import WireGuard


class JsonCollector(object):
    def __init__(self, interval=10):
        self.interval = interval
        self.wg = WireGuard() if module_loaded("wireguard") else WireGuardRead()

    def collect(self):
        # Fetch the JSON
        if check_if_file_exist("peers_info"):
            peers_info = read_tmp_file("peers_info")
            peers_info = format_results_for_controller(peers_info)
        else:
            peers_info = []
            time.sleep(1)
        peer_metadata = get_peer_metadata()
        for iface in peers_info:
            metric = Metric(f"interface_info_{iface['iface']}",
                            'interface_information', 'summary')
            for peer in iface['peers']:
                peer.update(peer_metadata.get(peer['public_key'], {}))
                for k, v in peer.items():
                    if k not in ['latency_ms', 'packet_loss', 'rx_bytes', 'tx_bytes']:
                        continue
                    metric.add_sample(f"iface_information_{k}",
                                      value=str(v),
                                      labels={
                                          'hostname': os.environ.get('SYNTROPY_AGENT_NAME', socket.gethostname()),
                                          'ifname': iface['iface'],
                                          'peer': peer['public_key'],
                                          'internal_ip': peer['internal_ip'],
                                          "device_id": peer.get('device_id'),
                                          "device_name": peer.get('device_name'),
                                          "device_public_ipv4": peer.get('device_public_ipv4')
                                      })
            yield metric


class  NetworkExporter(threading.Thread):

    def __init__(self, port=18001):
        super().__init__()
        self.stop_network_exporter = threading.Event()
        self.exporter_port = port
        self.daemon = True

    def run(self):
        start_http_server(self.exporter_port)
        REGISTRY.register(JsonCollector())
        while self.stop_network_exporter.is_set(): time.sleep(1)

    def join(self, timeout=None):
        self.stop_network_exporter.set()
        super().join(timeout)
