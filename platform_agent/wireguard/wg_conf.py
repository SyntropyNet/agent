import json
import os
import socket
import base64
import logging
import subprocess
import re
from pathlib import Path

import pyroute2
from pyroute2 import IPDB, WireGuard, NetlinkError
from nacl.public import PrivateKey

from platform_agent.cmd.iptables import add_iptable_rules, delete_iptable_rules, add_iptables_forward
from platform_agent.cmd.lsmod import module_loaded
from platform_agent.cmd.wg_show import get_wg_listen_port
from platform_agent.files.tmp_files import get_peer_metadata
from platform_agent.lib.ctime import now
from platform_agent.routes import Routes
from platform_agent.wireguard.helpers import find_free_port, get_peer_info, WG_NAME_PATTERN, WG_SYNTROPY_INT

logger = logging.getLogger()


class WgConfException(Exception):
    pass


def delete_interface(ifname):
    subprocess.run(['ip', 'link', 'del', ifname], check=False, stderr=subprocess.DEVNULL)



def create_interface(ifname):
    try:
        subprocess.run(['ip', 'link', 'add', 'dev', ifname, 'type', 'wireguard'], check=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass


def set_interface_up(ifname):
    try:
        subprocess.run(['ip', 'link', 'set', 'up', ifname], check=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass


def set_interface_ip(ifname, ip):
    try:
        subprocess.run(['ip', 'address', 'add', 'dev', ifname, ip], check=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass

class WgConf():

    def __init__(self, client=None):

        self.wg_kernel = module_loaded('wireguard')
        self.wg = WireGuard() if self.wg_kernel else WireguardGo()
        self.ipdb = IPDB()
        self.routes = Routes()
        self.client = client

    def create_syntropy_interfaces(self, ifaces):
        result = []
        if not ifaces:
            return result
        for ifname in ifaces.keys():
            int_data = self.create_interface("SYNTROPY_" + ifname, ifaces[ifname].get('internal_ip'), listen_port=ifaces[ifname].get('listen_port'))
            if int_data.get('public_key') != ifaces[ifname].get('public_key') or int_data.get('listen_port') != ifaces[ifname].get('listen_port'):
                result.append(
                    {
                        "fn": "create_interface",
                        "data": int_data
                    }
                )
        return result

    @staticmethod
    def get_wg_interfaces():
        with IPDB() as ipdb:
            current_interfaces = [k for k, v in ipdb.by_name.items() if re.match(WG_NAME_PATTERN, k) or k in WG_SYNTROPY_INT]
        return current_interfaces

    def clear_interfaces(self, dump, network_dump):
        remote_interfaces = [d['args']['ifname'] for d in dump if d['fn'] == 'create_interface']
        if network_dump:
            remote_interfaces.extend(["SYNTROPY_" + ifname for ifname in network_dump.keys()])
        current_interfaces = self.get_wg_interfaces()
        remove_interfaces = set(current_interfaces) - set(remote_interfaces)
        logger.debug(
            f"Clearing interfaces REMOTE - {remote_interfaces}, CURRENT - {current_interfaces} REMOVE={remove_interfaces}"
        )
        for interface in remove_interfaces:
            self.remove_interface(interface)

    def clear_unused_routes(self, dump):
        remote_peers = [d['args'] for d in dump if d['fn'] == 'add_peer']
        remote_interfaces = [d['args']['ifname'] for d in dump if d['fn'] == 'create_interface']
        for ifname in remote_interfaces:
            allowed_ips = []
            remote_peers = [allowed_ips.extend(peer['allowed_ips']) for peer in remote_peers if peer and peer['ifname'] == ifname]
            self.routes.clear_unused_routes(ifname, allowed_ips)


    def clear_peers(self, dump):
        remote_peers = [d['args']['public_key'] for d in dump if d['fn'] == 'add_peer']
        current_interfaces = self.get_wg_interfaces()
        for iface in current_interfaces:
            peers = get_peer_info(iface, self.wg)
            for peer in peers:
                if peer not in remote_peers:
                    self.remove_peer(iface, peer)

    def get_wg_keys(self, ifname):
        private_key_path = f"/etc/syntropy-agent/privatekey-{ifname}"
        public_key_path = f"/etc/syntropy-agent/publickey-{ifname}"
        private_key = Path(private_key_path)
        public_key = Path(public_key_path)
        if not private_key.is_file() or not public_key.is_file():
            privKey = PrivateKey.generate()
            pubKey = base64.b64encode(bytes(privKey.public_key))
            privKey = base64.b64encode(bytes(privKey))
            base64_privKey = privKey.decode('ascii')
            base64_pubKey = pubKey.decode('ascii')
            private_key.write_text(base64_privKey)
            public_key.write_text(base64_pubKey)
            private_key.chmod(0o600)
            public_key.chmod(0o600)

        if self.wg_kernel:
            return public_key.read_text().strip(), private_key.read_text().strip()
        else:
            return public_key.read_text().strip(), private_key_path

    def next_free_port(self, port=1024, max_port=65535):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while port <= max_port:
            try:
                sock.bind(('', port))
                sock.close()
                return port
            except OSError:
                port += 1
        raise IOError('no free ports')

    def create_interface(self, ifname, internal_ip, listen_port=None, **kwargs):
        public_key, private_key = self.get_wg_keys(ifname)
        peer_metadata = {'metadata': get_peer_metadata(public_key=public_key)}
        logger.info(
            f"[WG_CONF] - Creating interface {ifname}, {internal_ip} - wg_kernel={self.wg_kernel}",
            extra={'metadata': peer_metadata}
        )

        if self.wg_kernel:
            create_interface(ifname)
        else:
            self.wg.create_interface(ifname)
        set_interface_up(ifname)
        set_interface_ip(ifname, internal_ip)
        self.routes.clear_unused_iface_addrs(ifname, internal_ip.split('/')[0])

        if not listen_port:
            listen_port = find_free_port(bool('SDN' in ifname))
        try:
            self.wg.set(
                ifname,
                private_key=private_key,
                listen_port=listen_port
            )
        except NetlinkError as error:
            if error.code != 98:
                raise
            else:
                # if port was taken before creating.
                self.wg.set(
                    ifname,
                    private_key=private_key,
                )
        listen_port = self.get_listening_port(ifname)
        if not listen_port:
            listen_port = find_free_port(bool('SDN' in ifname))
            self.wg.set(
                ifname,
                private_key=private_key,
                listen_port=listen_port if listen_port else None
            )
        add_iptables_forward(ifname)
        result = {
            "public_key": public_key,
            "listen_port": int(listen_port),
            "ifname": ifname,
            "internal_ip": internal_ip
        }
        logger.debug(
            f"[WG_CONF] - interface_created {result}",
            extra={'metadata': peer_metadata}
        )
        return result

    def add_peer(self, ifname, public_key, allowed_ips, gw_ipv4, endpoint_ipv4=None, endpoint_port=None):
        peer_metadata = get_peer_metadata(public_key=public_key)
        if self.wg_kernel:
            try:
                peer_info = get_peer_info(ifname=ifname, wg=self.wg)
            except ValueError as e:
                raise WgConfException(str(e))
            old_ips = set(peer_info.get(public_key, [])) - set(allowed_ips)
            self.routes.ip_route_del(ifname, old_ips)
        peer = {'public_key': public_key,
                'persistent_keepalive': 15,
                'allowed_ips': allowed_ips}
        if endpoint_ipv4 and endpoint_port:
            peer.update(
                {
                    'endpoint_addr': endpoint_ipv4,
                    'endpoint_port': endpoint_port,
                }
            )
        self.wg.set(ifname, peer=peer)
        statuses = self.routes.ip_route_add(ifname, allowed_ips, gw_ipv4)
        add_iptable_rules(allowed_ips)
        data = {
                "connection_id": peer_metadata.get('connection_id'),
                "public_key": public_key,
                "statuses": statuses,
            }
        self.client.batch_send.queue.put({"data": data, "msg_type": 'WG_ROUTE_STATUS'})


    def remove_peer(self, ifname, public_key, allowed_ips=None):

        if ifname not in self.get_wg_interfaces():
            logger.debug(f'[WG_CONF] Remove peer - [{ifname}] does not exist')
            return

        peer = {
            'public_key': public_key,
            'remove': True
        }
        try:
            self.wg.set(ifname, peer=peer)
            if allowed_ips:
                self.routes.ip_route_del(ifname, allowed_ips)
                delete_iptable_rules(allowed_ips)
        except pyroute2.netlink.exceptions.NetlinkError as error:
            if error.code != 19:
                raise
        return

    def remove_interface(self, ifname):
        logger.debug(f'[WG_CONF] Removing interfcae - [{ifname}]')
        delete_interface(ifname)
        logger.debug(f'[WG_CONF] Removed interfcae - [{ifname}]')
        return

    def get_listening_port(self, ifname):
        if self.wg_kernel:
            wg_info = dict(self.wg.info(ifname)[0]['attrs'])
            return wg_info['WGDEVICE_A_LISTEN_PORT']

        else:
            wg_info = self.wg.info(ifname)
            return wg_info['listen_port']


class WireguardGo:

    def set(self, ifname, peer=None, private_key=None, listen_port=None):
        full_cmd = f"wg set {ifname}".split(' ')
        if peer:
            allowed_ips_cmd = ""
            endpoint = f"endpoint {peer['endpoint_addr']}:{peer.get('endpoint_port')} " if peer.get('endpoint_addr') else ""
            if not peer.get('remove'):
                for ip in peer.get('allowed_ips', []):
                    allowed_ips_cmd += f"allowed-ips {ip} "
                peer_cmd = f"peer {peer['public_key']} {allowed_ips_cmd}{endpoint}persistent-keepalive 15".split(
                    ' ')
            else:
                peer_cmd = f"peer {peer['public_key']} remove".split(' ')
            full_cmd += peer_cmd
        if private_key:
            private_key_cmd = f"private-key {private_key}".split(' ')
            full_cmd += private_key_cmd
            if not listen_port:
                listen_port = find_free_port()
        if listen_port:
            listen_port_cmd = f"listen-port {listen_port}".split(' ')
            full_cmd += listen_port_cmd

        result_set = subprocess.run(full_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        complete_output = result_set.stdout or result_set.stderr
        complete_output = complete_output or 'Success'
        logger.debug(f"[Wireguard-go] - WG SET - {complete_output} , args {full_cmd}")
        return complete_output

    def create_interface(self, ifname):
        try:
            result_set = subprocess.Popen(
                ['wireguard-go', ifname],
                encoding='utf-8',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            result_set.wait(timeout=2)
        except FileNotFoundError:
            raise WgConfException(f'Wireguard-go missing')
        complete_output = result_set.stdout or result_set.stderr
        complete_output = complete_output or 'Success'
        logger.debug(f"[Wireguard-go] - WG Create - {complete_output.read()} , args {ifname}")
        return complete_output

    def info(self, ifname):
        return {
            "listen_port": get_wg_listen_port(ifname)
        }
