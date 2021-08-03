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
        data = {"agent_id":3080,"network":{"PUBLIC":{"internal_ip":"10.69.14.97"},"SDN1":{"internal_ip":"10.69.14.98"},"SDN2":{"internal_ip":"10.69.14.99"},"SDN3":{"internal_ip":"10.69.14.100"}},"vpn":[{"fn":"add_peer","args":{"allowed_ips":["10.69.13.49/32","93.191.198.128/26"],"endpoint_ipv4":"149.6.144.90","endpoint_port":45543,"ifname":"PUBLIC","public_key":"G7gF5ZMgIe9GAnDedtg9ztb232tbrqaW4DUPUrqA5mo=","gw_ipv4":"10.69.14.97"},"metadata":{"device_id":"2210:51fc45b3-613b-4cde-b6ce-f1728f110f4b","device_name":"entain-pt1","device_public_ipv4":"149.6.144.90","connection_id":31034,"agent_id":2941,"link_tag":"PUBLIC","allowed_ips_info":[{"agent_service_name":"pt1","agent_service_tcp_ports":[],"agent_service_udp_ports":[],"agent_service_subnet_ip":"93.191.198.128/26"}]}},{"fn":"add_peer","args":{"allowed_ips":["10.69.10.61/32","2.58.8.64/26"],"endpoint_ipv4":"130.254.60.24","endpoint_port":45541,"ifname":"PUBLIC","public_key":"R2uT36XcKPkq4zGzQWAtZeKYHIypc1Ri07vdAFl5G0w=","gw_ipv4":"10.69.14.97"},"metadata":{"device_id":"2210:685da84d-185e-441d-b35b-10bc0c535db4","device_name":"entain-az1","device_public_ipv4":"130.254.60.24","connection_id":31094,"agent_id":2933,"link_tag":"PUBLIC","allowed_ips_info":[{"agent_service_name":"az1","agent_service_tcp_ports":[],"agent_service_udp_ports":[],"agent_service_subnet_ip":"2.58.8.64/26"}]}},{"fn":"add_peer","args":{"allowed_ips":["10.69.13.21/32","2.58.9.128/26"],"endpoint_ipv4":"64.127.192.50","endpoint_port":45544,"ifname":"PUBLIC","public_key":"BvreFU31yej02wOYieU9o8SZaNGLcEP/vLEWNnucTFM=","gw_ipv4":"10.69.14.97"},"metadata":{"device_id":"2210:bd5a0531-3bf5-452b-9ec3-3b505f2863a2","device_name":"entain-ill1","device_public_ipv4":"64.127.192.50","connection_id":31031,"agent_id":2932,"link_tag":"PUBLIC","allowed_ips_info":[{"agent_service_name":"ill1","agent_service_tcp_ports":[],"agent_service_udp_ports":[],"agent_service_subnet_ip":"2.58.9.128/26"}]}}]}
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
