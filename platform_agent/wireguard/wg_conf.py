import socket
import base64
import logging
import subprocess
from pathlib import Path

from pyroute2 import IPDB, WireGuard, IPRoute, NetlinkError
from nacl.public import PrivateKey

from platform_agent.cmd.lsmod import module_loaded
from platform_agent.cmd.rt_table import get_available_rt_table
from platform_agent.cmd.wg_show import get_wg_listen_port

logger = logging.getLogger()


class WgConfException(Exception):
    pass


class WgConf():

    def __init__(self):

        self.wg_kernel = module_loaded('wireguard')
        self.wg = WireGuard() if self.wg_kernel else WireguardGo()

    def get_wg_keys(self, ifname):
        private_key_path = f"/etc/wireguard/privatekey-{ifname}"
        public_key_path = f"/etc/wireguard/publickey-{ifname}"
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

    def create_interface(self, ifname, internal_ip, listen_port=None):
        logger.info(f"[WG_CONF] - Creating interface {ifname}")
        public_key, private_key = self.get_wg_keys(ifname)

        with IPDB() as ip:
            if self.wg_kernel:
                wg1 = ip.create(kind='wireguard', ifname=ifname)
            else:
                self.wg.create_interface(ifname)
                wg1 = ip.interfaces[ifname]
            wg1.add_ip(internal_ip)
            wg1.up()
            wg1.commit()
        self.wg.set(
            ifname,
            private_key=private_key,
            listen_port=listen_port
        )

        listen_port = self.get_listening_port(ifname)
        rt_table_id = get_available_rt_table()
        self.create_rule(internal_ip, rt_table_id)

        return {
            "public_key": public_key,
            "listen_port": listen_port,
            "rt_table_id": rt_table_id
        }

    def add_peer(self, ifname, public_key, allowed_ips, gw_ipv4, rt_table_id=None, endpoint_ipv4=None, endpoint_port=None):
        peer = {'public_key': public_key,
                'endpoint_addr': endpoint_ipv4,
                'endpoint_port': endpoint_port,
                'persistent_keepalive': 15,
                'allowed_ips': allowed_ips}
        self.wg.set(ifname, peer=peer)
        self.ip_route_add(ifname, allowed_ips, gw_ipv4)
        if rt_table_id:
            self.create_routes(allowed_ips, gw_ipv4, rt_table_id)
        return

    def remove_peer(self, ifname, public_key, allowed_ips):
        peer = {
            'public_key': public_key,
            'remove': True
            }

        self.wg.set(ifname, peer=peer)
        self.ip_route_del(ifname, allowed_ips)
        return

    def remove_interface(self, ifname):
        with IPDB() as ipdb:
            if ifname not in ipdb.interfaces:
                raise WgConfException(f'[{ifname}] does not exist')
            with ipdb.interfaces[ifname] as i:
                i.remove()
        return

    def ip_route_add(self, ifname, ip_list, gw_ipv4):
        ip_route = IPRoute()
        devices = ip_route.link_lookup(ifname=ifname)
        dev = devices[0]
        for ip in ip_list:
            try:
                ip_route.route('add', dst=ip, gateway=gw_ipv4, oif=dev)
            except NetlinkError as error:
                if error.code != 17:
                    raise
                logger.info(f"[WG_CONF] add route failed [{ip}] - already exists")

    def ip_route_del(self, ifname, ip_list, scope=None):
        ip_route = IPRoute()
        devices = ip_route.link_lookup(ifname=ifname)
        dev = devices[0]
        for ip in ip_list:
            try:
                ip_route.route('del', dst=ip, oif=dev, scope=scope)
            except NetlinkError as error:
                if error.code != 17:
                    raise
                logger.info(f"[WG_CONF] del route failed [{ip}] - does not exist")

    def get_listening_port(self, ifname):
        if self.wg_kernel:
            wg_info = dict(self.wg.info(ifname)[0]['attrs'])
            return wg_info['WGDEVICE_A_LISTEN_PORT']

        else:
            wg_info = self.wg.info(ifname)
            return wg_info['listen_port']

    def create_rule(self, internal_ip, rt_table_id):
        ip_route = IPRoute()
        ip_route.flush_rules(table=rt_table_id)
        ip_route.flush_routes(table=rt_table_id)
        ip_route.rule('add', src=internal_ip, table=rt_table_id)

    def create_routes(self, destination_ips, gw, rt_table_id):
        ip_route = IPRoute()
        for destination_ip in destination_ips:
            ip_route.route('add', dst=destination_ip, gateway=gw, table=rt_table_id)


class WireguardGo():

    def set(self, ifname, peer=None, private_key=None, listen_port=None):
        full_cmd = f"wg set {ifname}".split(' ')
        if peer:
            allowed_ips_cmd = ""
            if not peer.get('remove'):
                for ip in peer.get('allowed_ips', []):
                    allowed_ips_cmd += f"allowed-ips {ip} "
                peer_cmd = f"peer {peer['public_key']} {allowed_ips_cmd}endpoint {peer['endpoint_addr']}:{peer['endpoint_port']}".split(' ')
            else:
                peer_cmd = f"peer {peer['public_key']} remove"
            full_cmd += peer_cmd
        if private_key:
            private_key_cmd = f"private-key {private_key}".split(' ')
            full_cmd += private_key_cmd
        if listen_port:
            listen_port_cmd = f"listen-port {listen_port}".split(' ')
            full_cmd += listen_port_cmd

        result_set = subprocess.run(full_cmd, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        complete_output = result_set.stdout or result_set.stderr
        complete_output = complete_output or 'Success'
        logger.info(f"[Wireguard-go] - WG SET - {complete_output} , args {full_cmd}")
        return complete_output

    def create_interface(self, ifname):
        result_set = subprocess.run(['wireguard-go', ifname], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        complete_output = result_set.stdout or result_set.stderr
        complete_output = complete_output or 'Success'
        return complete_output

    def info(self, ifname):
        return {
            "listen_port": get_wg_listen_port(ifname)
        }