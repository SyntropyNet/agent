import time
import json
import threading
import re

from platform_agent.files.tmp_files import read_tmp_file
from platform_agent.wireguard.helpers import WG_NAME_PATTERN, WG_SYNTROPY_INT
from platform_agent.lib.ctime import now


class BWDataCollect(threading.Thread):

    def __init__(self, client, interval=120):
        super().__init__()
        self.interval = interval
        self.client = client
        self.stop_BWDataCollect = threading.Event()
        self.daemon = True

    @staticmethod
    def get_int_info(t, iface):
        try:
            with open('/sys/class/net/' + iface + '/statistics/' + t, 'r') as f:
                data = f.read()
                return int(data)
        except FileNotFoundError:
            return -1

    @staticmethod
    def get_iface_info_set(iface, interval=10):
        tx_bytes = BWDataCollect.get_int_info('tx_bytes', iface)
        rx_bytes = BWDataCollect.get_int_info('rx_bytes', iface)

        tx_dropped = BWDataCollect.get_int_info('tx_dropped', iface)
        tx_errors = BWDataCollect.get_int_info('tx_errors', iface)
        tx_packets = BWDataCollect.get_int_info('tx_packets', iface)

        rx_dropped = BWDataCollect.get_int_info('rx_dropped', iface)
        rx_errors = BWDataCollect.get_int_info('rx_errors', iface)
        rx_packets = BWDataCollect.get_int_info('rx_packets', iface)

        time.sleep(interval)

        tx_bytes_after = BWDataCollect.get_int_info('tx_bytes', iface)
        rx_bytes_after = BWDataCollect.get_int_info('rx_bytes', iface)

        tx_dropped_after = BWDataCollect.get_int_info('tx_dropped', iface)
        tx_errors_after = BWDataCollect.get_int_info('tx_errors', iface)
        tx_packets_after = BWDataCollect.get_int_info('tx_packets', iface)

        rx_dropped_after = BWDataCollect.get_int_info('rx_dropped', iface)
        rx_errors_after = BWDataCollect.get_int_info('rx_errors', iface)
        rx_packets_after = BWDataCollect.get_int_info('rx_packets', iface)


        tx_speed_mbps = round((tx_bytes_after - tx_bytes) / 10000000.0, 4) * -1
        rx_speed_mbps = round((rx_bytes_after - rx_bytes) / 10000000.0, 4)
        tx_dropped = (tx_dropped_after - tx_dropped)
        tx_errors = (tx_errors_after - tx_errors)
        tx_packets = (tx_packets_after - tx_packets)
        rx_dropped = (rx_dropped_after - rx_dropped)
        rx_errors = (rx_errors_after - rx_errors)
        rx_packets = (rx_packets_after - rx_packets)
        return {
            'iface': iface,
            'tx_speed_mbps': tx_speed_mbps,
            'rx_speed_mbps': rx_speed_mbps,
            'tx_dropped': tx_dropped,
            'tx_errors': tx_errors,
            'tx_packets': tx_packets,
            'rx_dropped': rx_dropped,
            'rx_errors': rx_errors,
            'rx_packets': rx_packets,
            'interval': interval,
        }

    def run(self):
        while not self.stop_BWDataCollect.is_set():
            interfaces = read_tmp_file(file_type='iface_info')
            wg_ifaces = {k: v for k, v in interfaces.items() if re.match(WG_NAME_PATTERN, k) or k in WG_SYNTROPY_INT}
            if not wg_ifaces:
                time.sleep(1)
            for iface in wg_ifaces:
                try:
                    result = [self.get_iface_info_set(iface, self.interval)]
                except FileNotFoundError:
                    continue
                if not result:
                    continue
                self.client.send_log(json.dumps({
                    'id': "UNKNOWN",
                    'executed_at': now(),
                    'type': 'IFACES_BW_DATA',
                    'data': result
                }))
                time.sleep(int(self.interval))

    def join(self, timeout=None):
        self.stop_BWDataCollect.set()
        super().join(timeout)