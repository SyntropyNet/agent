import json
import logging
import threading
import time
from pyroute2 import WireGuard

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.lib.ctime import now
from platform_agent.lib.file_helper import check_if_file_exist, read_tmp_file, format_results_for_controller
from platform_agent.cmd.wg_info import WireGuardRead

logger = logging.getLogger()


class WireguardPeerWatcher(threading.Thread):

    def __init__(self, client, interval=60):
        super().__init__()
        self.client = client
        self.interval = interval
        self.wg = WireGuard() if module_loaded("wireguard") else WireGuardRead()
        self.stop_peer_watcher = threading.Event()
        self.daemon = True

    def run(self):
        while not self.stop_peer_watcher.is_set():
            if check_if_file_exist("peers_info"):
                peers_info = read_tmp_file("peers_info")
            else:
                time.sleep(1)
                continue
            self.client.send(json.dumps({
                'id': "-",
                'executed_at': now(),
                'type': 'IFACES_PEERS_BW_DATA',
                'data': format_results_for_controller(peers_info),
            }))
            time.sleep(int(self.interval))

    def join(self, timeout=None):
        self.stop_peer_watcher.set()
        super().join(timeout)
