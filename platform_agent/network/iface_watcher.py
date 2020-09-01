import logging
import threading
import time
import json

import pyroute2

from platform_agent.config.settings import AGENT_PATH_TMP

logger = logging.getLogger()

WG_NAME_SUBSTRINGS = ['p2p_', 'mesh_', 'gw_']


def read_tmp_file(file_type='iface_info'):
    """Read iface file"""
    try:
        with open(f"{AGENT_PATH_TMP}/{file_type}") as json_file:
            rez = json_file.read()
            try:
                data = json.loads(rez)
            except json.JSONDecodeError:
                data = {}
    except FileNotFoundError:
        data = {}
    return data


class InterfaceWatcher(threading.Thread):

    def __init__(self):
        super().__init__()
        self.iface_watcher = threading.Event()
        self.watcher = threading.Event()
        self.daemon = True

    def update_iface_info_file(self, data):
        iface_info_path = f"{AGENT_PATH_TMP}/iface_info"
        with open(iface_info_path, 'w+') as iface_info_file:
            json.dump(data, iface_info_file)
            iface_info_file.close()

    def run(self):
        while not self.iface_watcher.is_set():
            with pyroute2.IPDB() as ipdb:
                res = {k: v for k, v in ipdb.by_name.items()}
                payload = {}
                for ifname in res.keys():
                    if not res[ifname].get('ipaddr'):
                        continue
                    internal_ip = f"{res[ifname]['ipaddr'][0]['address']}/{res[ifname]['ipaddr'][0]['prefixlen']}"
                    payload[ifname] = {
                        'internal_ip': internal_ip,
                        'kind': res[ifname]['kind']
                    }
                self.update_iface_info_file(payload)
                time.sleep(1)

    def join(self, timeout=None):
        self.watcher.set()
        super().join(timeout)
