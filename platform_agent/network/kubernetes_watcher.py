import json
import logging
import threading
import time

from platform_agent.lib.ctime import now
from pyroute2 import IPDB
from kubernetes import client, config

logger = logging.getLogger()


class KubernetesConfigException(Exception):
    pass


class KubernetesNetworkWatcher(threading.Thread):

    def __init__(self, ws_client):
        super().__init__()
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            try:
                config.load_kube_config()
            except config.config_exception.ConfigException:
                raise KubernetesConfigException("Couldn't find config")
        self.v1 = client.CoreV1Api()
        self.ws_client = ws_client
        self.stop_kubernetes_watcher = threading.Event()
        self.interval = 10

        with IPDB() as ipdb:
            self.ifaces = [k for k, v in ipdb.by_name.items() if any(
                substring in k for substring in ['noia_'])]
        self.daemon = True

    def run(self):
        ex_result = []
        while not self.stop_kubernetes_watcher.is_set():
            result = []
            ret = self.v1.list_pod_for_all_namespaces()
            for i in ret.items:
                result.append(
                    {
                        'agent_network_subnets': f"{i.status.pod_ip}/32",
                        'agent_network_name': i.metadata.name,
                    }
                )
                if result != ex_result:
                    self.ws_client.send(json.dumps({
                        'id': "ID." + str(time.time()),
                        'executed_at': now(),
                        'type': 'KUBERNETES_NETWORK_INFO',
                        'data': result
                    }))
                    ex_result = result
            time.sleep(10)

    def join(self, timeout=None):
        self.stop_kubernetes_watcher.set()
        super().join(timeout)
