import logging
import threading
import time
from datetime import datetime
from pyroute2 import WireGuard

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.lib.file_helper import check_if_file_exist, update_file, read_tmp_file
from platform_agent.wireguard.helpers import merged_peer_info, get_connection_status
from platform_agent.cmd.wg_info import WireGuardRead

logger = logging.getLogger()


class WireguardPeerDataCollector(threading.Thread):

    def __init__(self, client, interval=5):
        super().__init__()
        self.client = client
        self.interval = interval
        self.wg = WireGuard() if module_loaded("wireguard") else WireGuardRead()
        self.stop_peer_data_collector = threading.Event()
        self.daemon = True

    @staticmethod
    def calculate_bw(old_peers_info, new_peers_info, packet_loss):
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
                    new_peer.update(packet_loss[new_peer['internal_ip']])
                    new_peers_info[iface]['peers'][peer_public_key] = new_peer
                except KeyError:  # if peer does not exist in old, just skip and don't calculate bw
                    continue
        return new_peers_info


    @staticmethod
    def calculate_packet_loss(last_x_pings):
        result = {}
        for ping in last_x_pings:
            for internal_ip, data in ping.items():
                if not result.get(internal_ip):
                    result[internal_ip] = {}
                    result[internal_ip]['packet_loss'] = data['packet_loss']
                    result[internal_ip].update(
                        get_connection_status(data['latency_ms'], result[internal_ip]['packet_loss']))
                result[internal_ip]['packet_loss'] = (result[internal_ip]['packet_loss'] + data['packet_loss']) / 2
                result[internal_ip].update(get_connection_status(data['latency_ms'], result[internal_ip]['packet_loss']))
        return result

    def run(self):
        last_x_pings = []
        last_pings_amount = 5
        while not self.stop_peer_data_collector.is_set():
            peer_info, pings = merged_peer_info(self.wg)
            if not pings:
                time.sleep(1)
                continue
            last_x_pings.insert(0, pings)
            last_x_pings = last_x_pings[:last_pings_amount]
            packet_loss = self.calculate_packet_loss(last_x_pings)
            if check_if_file_exist("peers_info"):
                old_peers_info = read_tmp_file("peers_info")
                peer_info = self.calculate_bw(old_peers_info, peer_info, packet_loss)
            update_file('peers_info', peer_info)

    def join(self, timeout=None):
        self.stop_peer_data_collector.set()
        super().join(timeout)
