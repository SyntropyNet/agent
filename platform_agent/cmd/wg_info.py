import re
import os
import json

import dataclasses
from typing import List


class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


@dataclasses.dataclass
class WgPeer:
    peer: str
    allowed_ips: List[str]
    preshared_key: str = None
    endpoint: str = None
    latest_handshake: str = None
    persistent_keepalive: str = None
    transfer: str = None


@dataclasses.dataclass
class WgInterface:
    interface: str
    listening_port: str = None
    private_key: str = None
    public_key: str = None
    peers: List[WgPeer] = dataclasses.field(default_factory=[])


class WireGuardRead:
    def __init__(self):
        self.interface_regex = r'((?:[^\n][\n]?)+)'
        self.parameter_regex = r'(^.+): (.+$)'
        self.stdin = None

    def wg_info(self, ifname=None):
        if ifname:
            grep = f" {ifname}"
        else:
            grep = ""
        self.stdin = os.popen('wg show' + grep).read()
        output = []
        for i in map(self.make_json, self.all_interfaces()):
            if 'interface' in i:
                interface = WgInterface(peers=[], **i)
                output.append(interface)
            else:
                interface.peers.append(WgPeer(**i))
        output = json.loads(json.dumps(output, cls=DataclassJSONEncoder))
        return output

    def all_interfaces(self):
        interfaces = re.findall(self.interface_regex, self.stdin, re.MULTILINE)
        if interfaces:
            return interfaces
        else:
            return []

    def format_value(self, key, value):
        key = self.format_key(key)
        array_format = ['allowed_ips']

        if key in array_format:
            value = value.split(', ')

        return value

    @staticmethod
    def format_key(key):
        return key.replace('  ', '').replace(' ', '_')

    def make_json(self, s):
        confing = re.findall(self.parameter_regex, s, re.MULTILINE)
        return {self.format_key(key): self.format_value(key, value) for key, value in confing}
