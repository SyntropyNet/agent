import json
import logging
import threading
import os

from platform_agent.cmd.iptables import iptables_create_syntropy_chain
from platform_agent.lib.ctime import now
from platform_agent.cmd.lsmod import module_loaded
from platform_agent.files.tmp_files import update_tmp_file
from platform_agent.lib.get_info import gather_initial_info
from platform_agent.network.exporter import NetworkExporter
from platform_agent.network.kubernetes_watcher import KubernetesNetworkWatcher
from platform_agent.wireguard import WgConfException, WgConf, WireguardPeerWatcher
from platform_agent.docker_api.docker_api import DockerNetworkWatcher
from platform_agent.network.dummy_watcher import DummyNetworkWatcher
from platform_agent.executors.wg_exec import WgExecutor
from platform_agent.network.network_info import BWDataCollect
from platform_agent.network.autoping import AutopingClient
from platform_agent.network.iperf import IperfServer
from platform_agent.network.iface_watcher import InterfaceWatcher
from platform_agent.rerouting.rerouting import Rerouting

logger = logging.getLogger()


class AgentApi:

    def __init__(self, runner, prod_mode=True):
        self.runner = runner
        self.wg_peers = None
        self.autoping = None
        self.wgconf = WgConf(self.runner)
        self.wg_executor = WgExecutor(self.runner)
        self.bw_data_collector = BWDataCollect(self.runner)
        if prod_mode:
            threading.Thread(target=self.wg_executor.run).start()
            threading.Thread(target=self.bw_data_collector.run).start()
            self.network_exporter = NetworkExporter().start()
            self.wg_peers = WireguardPeerWatcher(self.runner).start()
            self.interface_watcher = InterfaceWatcher().start()
            if module_loaded("wireguard"):
                os.environ["SYNTROPY_WIREGUARD"] = "true"
            if os.environ.get("SYNTROPY_NETWORK_API", '').lower() == "docker" and prod_mode:
                iptables_create_syntropy_chain()
                self.network_watcher = DockerNetworkWatcher(self.runner).start()
            if os.environ.get("SYNTROPY_NETWORK_API", '').lower() == "host" and prod_mode:
                self.network_watcher = DummyNetworkWatcher(self.runner).start()
            if os.environ.get("SYNTROPY_NETWORK_API", '').lower() == "kubernetes" and prod_mode:
                self.network_watcher = KubernetesNetworkWatcher(self.runner).start()
            self.rerouting = Rerouting(self.runner).start()

    def call(self, type, data, request_id):
        result = None
        try:
            if hasattr(self, type):
                if not isinstance(data, (dict, list)):
                    logger.error('[AGENT_API] data should be "DICT" type')
                    result = {'error': "BAD REQUEST"}
                else:
                    fn = getattr(self, type)
                    result = fn(data, request_id=request_id)
        except AttributeError as error:
            logger.warning(error)
            result = {'error': str(error)}
        return result

    def GET_INFO(self, data, **kwargs):
        return gather_initial_info(**data)

    def WG_INFO(self, data, **kwargs):
        if self.wg_peers:
            self.wg_peers.join(timeout=1)
            self.wg_peers = None
        self.wg_peers = WireguardPeerWatcher(self.runner, **data)
        self.wg_peers.start()

    def WG_CONF(self, data, **kwargs):
        self.wg_executor.queue.put({"data": data, "request_id": kwargs['request_id']})
        return False

    def AUTO_PING(self, data, **kwargs):
        if self.autoping:
            self.autoping.join(timeout=1)
            self.autoping = None
        self.autoping = AutopingClient(self.runner, **data)
        self.autoping.start()
        return False

    def CONFIG_INFO(self, data, **kwargs):
        update_tmp_file(data, 'config_dump')
        self.wgconf.clear_interfaces(data.get('vpn', []), data.get("network", {}))
        self.wgconf.clear_peers(data.get('vpn', []))
        self.wgconf.clear_unused_routes(data.get('vpn', []))
        response = self.wgconf.create_syntropy_interfaces(data.get("network", {}))
        for vpn_cmd in data.get('vpn', []):
            try:
                fn = getattr(self.wgconf, vpn_cmd['fn'])
                result = fn(**vpn_cmd['args'])
                if vpn_cmd['fn'] == 'create_interface' and result and\
                        (vpn_cmd['args'].get('public_key') != result.get('public_key') or
                         vpn_cmd['args'].get('listen_port') != result.get('listen_port')):
                    response.append({'fn': vpn_cmd['fn'], 'data': result})
            except WgConfException as e:
                logger.error(f"[CONFIG_INFO] [{str(e)}]")
        self.runner.send(json.dumps({
            'id': kwargs['request_id'],
            'executed_at': now(),
            'type': 'UPDATE_AGENT_CONFIG',
            'data': response
        }))

    def IPERF_SERVER(self, data, **kwargs):
        if self.iperf and data.get('status') == 'off':
            self.iperf.join(timeout=1)
            self.iperf = None
            return 'ok'
        if data.get('status'):
            self.iperf = IperfServer()
            IperfServer.start(self.runner)
            return 'ok'

    def IPERF_TEST(self, data, **kwargs):
        if data.get('hosts') and isinstance(data['hosts'], list):
            result = IperfServer.test_speed(**data)
            return result
        else:
            return {"error": "must be list"}
