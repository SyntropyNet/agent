import json
import logging
import threading
import time
from datetime import datetime
from pyroute2 import WireGuard

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.lib.ctime import now
from platform_agent.lib.file_helper import check_if_file_exist, update_file, read_tmp_file
from platform_agent.wireguard.helpers import merged_peer_info
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

    @staticmethod
    def calculate_bw(old_peers_info, new_peers_info):
        for iface in old_peers_info.keys():
            for peer_public_key in old_peers_info[iface]['peers'].keys():
                try:
                    new_peer = new_peers_info[iface]['peers'][peer_public_key]
                    old_peer = old_peers_info[iface]['peers'][peer_public_key]
                    time_diff = (datetime.fromtimestamp(new_peer['timestamp']) - datetime.fromtimestamp(
                        old_peer['timestamp'])).total_seconds()
                    rx_speed_mbps = ((new_peer['rx_bytes'] - old_peer['rx_bytes']) / 1000000) / time_diff
                    new_peer['rx_speed_mbps'] = rx_speed_mbps
                    tx_speed_mpbs = -1 * (((new_peer['tx_bytes'] - old_peer['tx_bytes']) / 1000000) / time_diff)
                    new_peer['tx_speed_mbps'] = tx_speed_mpbs
                    new_peers_info[iface]['peers'][peer_public_key] = new_peer
                except KeyError:  # if peer does not exist in old, just skip and don't calculate bw
                    continue
        return new_peers_info

    @staticmethod
    def format_results_for_controller(peer_info):
        result = []
        for iface in peer_info.keys():
            result.append(
                {
                    "iface": iface,
                    "iface_public_key": peer_info[iface]['iface_public_key'],
                    "peers": list(peer_info[iface]['peers'].values())
                }
            )
        return result

    def run(self):
        while not self.stop_peer_watcher.is_set():
            peer_info = merged_peer_info(self.wg)
            if check_if_file_exist("peers_info"):
                old_peers_info = read_tmp_file("peers_info")
                peer_info = self.calculate_bw(old_peers_info, peer_info)
            update_file('peers_info', peer_info)
            if not peer_info:
                time.sleep(1)
                continue
            self.client.send_log(json.dumps({
                'id': "UNKNOWN",
                'executed_at': now(),
                'type': 'IFACES_PEERS_BW_DATA',
                'data': self.format_results_for_controller(peer_info),
            }))
            time.sleep(int(self.interval))

    def join(self, timeout=None):
        self.stop_peer_watcher.set()
        super().join(timeout)
