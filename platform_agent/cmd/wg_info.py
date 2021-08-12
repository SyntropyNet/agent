import re
import os
import json

import dataclasses
from datetime import datetime
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
    tx_bytes: str = None
    rx_bytes: str = None
    timestamp: str = None

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

    def get_bytes(self, transfer):
        bytes = transfer.split(', ')
        rx_bytes = bytes[0]
        tx_bytes = bytes[1]
        if "k" in rx_bytes.lower():
            rx_bytes = float(rx_bytes.split(' ')[0]) * 1000
        elif "m" in rx_bytes.lower():
            rx_bytes = float(rx_bytes.split(' ')[0]) * 1000000
        elif "g" in rx_bytes.lower():
            rx_bytes = float(rx_bytes.split(' ')[0]) * 1000000 * 1000
        if "k" in tx_bytes.lower():
            tx_bytes = float(tx_bytes.split(' ')[0]) * 1000
        elif "m" in tx_bytes.lower():
            tx_bytes = float(tx_bytes.split(' ')[0]) * 1000000
        elif "g" in tx_bytes.lower():
            tx_bytes = float(tx_bytes.split(' ')[0]) * 1000000 * 1000
        if type(rx_bytes) == str:
            rx_bytes = 0
        if type(tx_bytes) == str:
            tx_bytes = 0
        return rx_bytes, tx_bytes

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
                data = WgPeer(**i)
                rx_bytes, tx_bytes = self.get_bytes(data.transfer)
                data.rx_bytes = rx_bytes
                data.tx_bytes = tx_bytes
                data.timestamp = datetime.now().timestamp()
                interface.peers.append(data)
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
