import json
import logging
import threading
import time

import docker
from requests.exceptions import ConnectionError
from urllib3.exceptions import ProtocolError

from platform_agent.docker_api.helpers import format_networks_result, format_container_result
from platform_agent.lib.ctime import now
from platform_agent.cmd.iptables import delete_iptable_rules

logger = logging.getLogger()


class DockerNetworkWatcher(threading.Thread):

    def __init__(self, ws_client):
        super().__init__()
        self.ws_client = ws_client
        self.docker_client = docker.from_env()
        try:
            self.events = self.docker_client.events(decode=True)
        except (ConnectionError, ProtocolError) as e:
            logger.error(f"[DOCKER_API]: {e}")
            self.events = []
        self.daemon = True

    def run(self):
        old_res = []
        for event in self.events:
            if event.get('Type') == 'network' and event.get('Action') in ['create', 'destroy']:
                networks = self.docker_client.networks()
                result = format_networks_result(networks)
                if old_res == result:
                    continue
                logger.debug(f"[NETWORK_INFO] Sending networks {result}")
                self.ws_client.send(json.dumps({
                    'id': "ID." + str(time.time()),
                    'executed_at': now(),
                    'type': 'NETWORK_INFO',
                    'data': result
                }))
                old_res = result
            if event.get('Type') == 'container' and event.get('Action') in ['create', 'destroy', 'stop', 'start']:
                containers = self.docker_client.containers()
                result = format_container_result(containers)
                if old_res == result:
                    continue
                self.ws_client.send(json.dumps({
                    'id': "ID." + str(time.time()),
                    'executed_at': now(),
                    'type': 'CONTAINER_INFO',
                    'data': result
                }))
                if event.get('Action') in ['destroy', 'stop']:
                    for container in old_res:
                        if container.get('agent_container_id') and container.get('agent_container_id') == event.get('id'):
                            delete_iptable_rules(container['agent_container_ips'])
                old_res = result


    def join(self, timeout=None):
        self.events.close()
        super().join(timeout)
