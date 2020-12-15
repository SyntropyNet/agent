from prometheus_client import start_http_server, Metric, REGISTRY
from platform_agent.network.network_info import BWDataCollect
from platform_agent.wireguard.wg_conf import WgConf

import json
import requests
import sys
import time
import socket
import os


class JsonCollector(object):
    def __init__(self, interval=10):
        self.interval = interval

    def collect(self):
        # Fetch the JSON
        for iface in WgConf.get_wg_interfaces():
            result = BWDataCollect.get_iface_info_set(iface, self.interval)
            del result['iface']
            metric = Metric(f'interface_info_{iface}',
                            'interface_information', 'summary')
            # Convert requests and duration to a summary in seconds
            for k, v in result.items():
                print(k, v)
                metric.add_sample(f'interface_information_{k}',
                                  value=str(v), labels={'hostname': os.environ.get('SYNTROPY_AGENT_NAME', socket.gethostname()), 'interval': str(self.interval)})
            yield metric


if __name__ == '__main__':
    # Usage: json_exporter.py port endpoint
    start_http_server(1234)
    REGISTRY.register(JsonCollector())
    while True: time.sleep(1)
