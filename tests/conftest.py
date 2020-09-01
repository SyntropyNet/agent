from pytest import fixture


@fixture
def CONFIG_INFO():
    return 'CONFIG_INFO'


@fixture
def GET_INFO():
    return 'GET_INFO'


@fixture
def WG_INFO():
    return 'WG_INFO'


@fixture
def request_id():
    return 'TEST_01'


@fixture
def wg_int_name():
    return 'p2p_agent'


@fixture
def config_info_int_check():
    return {'agent_id': 71, 'vpn': [
        {'args': {'ifname': 'p2p_15_g8y3', 'internal_ip': '10.69.0.22/31'}, 'fn': 'create_interface'},
        {'args': {'ifname': 'mesh_111_v2t6', 'internal_ip': '10.69.0.35/31'}, 'fn': 'create_interface'},
        {'args': {'ifname': 'gw_113_d5yg', 'internal_ip': '10.69.0.56/31'}, 'fn': 'create_interface'},
        {'args': {'ifname': 'mesh_112_wnyt', 'internal_ip': '10.69.0.48/31'}, 'fn': 'create_interface'}
    ]}


@fixture
def gather_initial_info_payload():
    return {}


@fixture
def gather_initial_info_payload_bad():
    return "BAD_PAYLOAD"


@fixture
def wg_info_payload():
    return {'interval': 5}


@fixture
def mock_wg_show():
    return ('interface: mesh_8_qazm\n'
            '  public key: /c2PsNqVkbKJnvcdNeh4itIBpsZYNMLksUtXGIRgSDc=\n'
            '  private key: (hidden)\n'
            '  listening port: 43345\n'
            '\n'
            'peer: lh9VWZKS8Vu4b3QTJMuLAajvYJqO6GD9orMt8TQUWhE=\n'
            '  endpoint: 40.85.151.171:41152\n'
            '  allowed ips: 10.69.0.12/32, 192.168.151.0/24\n'
            '  transfer: 0 B received, 2.79 MiB sent\n'
            '  persistent keepalive: every 15 seconds\n'
            '\n'
            'peer: RNlLq4YM2jXwZ3r9uAXOBf+zbYrqImndeLjAqIZLRGI=\n'
            '  endpoint: 140.238.215.51:51783\n'
            '  allowed ips: 10.69.0.11/32\n'
            '  transfer: 0 B received, 2.79 MiB sent\n'
            '  persistent keepalive: every 15 seconds\n'
            '\n'
            'peer: qlkykBhjGpuJkyayQJMw5fyLZyTGFfRTTnuXQLBhPQQ=\n'
            '  endpoint: 13.93.72.56:33632\n'
            '  allowed ips: 10.69.0.13/32, 172.17.0.0/16, 192.168.152.0/24, '
            '192.168.154.0/24\n'
            '  transfer: 0 B received, 2.79 MiB sent\n'
            '  persistent keepalive: every 15 seconds\n')


@fixture
def wg_show_dict():
    return [{'interface': 'mesh_8_qazm',
             'listening_port': '43345',
             'peers': [{'allowed_ips': ['10.69.0.12/32', '192.168.151.0/24'],
                        'endpoint': '40.85.151.171:41152',
                        'latest_handshake': None,
                        'peer': 'lh9VWZKS8Vu4b3QTJMuLAajvYJqO6GD9orMt8TQUWhE=',
                        'persistent_keepalive': 'every 15 seconds',
                        'preshared_key': None,
                        'transfer': '0 B received, 2.79 MiB sent'},
                       {'allowed_ips': ['10.69.0.11/32'],
                        'endpoint': '140.238.215.51:51783',
                        'latest_handshake': None,
                        'peer': 'RNlLq4YM2jXwZ3r9uAXOBf+zbYrqImndeLjAqIZLRGI=',
                        'persistent_keepalive': 'every 15 seconds',
                        'preshared_key': None,
                        'transfer': '0 B received, 2.79 MiB sent'},
                       {'allowed_ips': ['10.69.0.13/32',
                                        '172.17.0.0/16',
                                        '192.168.152.0/24',
                                        '192.168.154.0/24'],
                        'endpoint': '13.93.72.56:33632',
                        'latest_handshake': None,
                        'peer': 'qlkykBhjGpuJkyayQJMw5fyLZyTGFfRTTnuXQLBhPQQ=',
                        'persistent_keepalive': 'every 15 seconds',
                        'preshared_key': None,
                        'transfer': '0 B received, 2.79 MiB sent'}],
             'private_key': '(hidden)',
             'public_key': '/c2PsNqVkbKJnvcdNeh4itIBpsZYNMLksUtXGIRgSDc='}]


@fixture
def agent_dump():
    return \
        {
            "agent_id": 30,
            "vpn": [
                {
                    "fn": "create_interface",
                    "args": {
                        "ifname": "pmesh_51_eg0r",
                        "internal_ip": "10.69.0.10/32",
                        "listen_port": 57950
                    }
                },
                {
                    "fn": "add_peer",
                    "args": {
                        "allowed_ips": [
                            "10.69.0.11/32",
                            "192.168.151.0/24"
                        ],
                        "endpoint_ipv4": "23.99.200.18",
                        "endpoint_port": 50848,
                        "ifname": "pmesh_51_eg0r",
                        "public_key": "EhFJfT0UelKZRoYITH3NHyZmCPmvO85n7Fmw2wuwTBI=",
                        "gw_ipv4": "10.69.0.10"
                    },
                    "metadata": {
                        "device_id": "1123",
                        "device_name": "device_name",
                        "device_public_ipv4": "72.5.6.4"
                    }
                },
                {
                    "fn": "create_interface",
                    "args": {
                        "ifname": "smesh_51_eyus",
                        "internal_ip": "10.69.0.12/32",
                        "listen_port": 48849
                    }
                },
                {
                    "fn": "add_peer",
                    "args": {
                        "allowed_ips": [
                            "10.69.0.13/32",
                            "192.168.151.0/24"
                        ],
                        "endpoint_ipv4": "159.8.21.106",
                        "endpoint_port": 15566,
                        "ifname": "smesh_51_eyus",
                        "public_key": "EX19IgQzdPkM1tsfvSv+XOhhQ8JD/Q13e+i/H26K53U=",
                        "gw_ipv4": "10.69.0.12"
                    },
                    "metadata": {
                        "device_id": "9993",
                        "device_name": "9993-agent",
                        "device_public_ipv4": "73.5.6.4"
                    }
                }
            ]
        }


@fixture
def peer_file_read():
    return {
        "EhFJfT0UelKZRoYITH3NHyZmCPmvO85n7Fmw2wuwTBI=": {
            "device_id": "1123",
            "device_name": "device_name",
            "device_public_ipv4": "72.5.6.4"
        },
        "EX19IgQzdPkM1tsfvSv+XOhhQ8JD/Q13e+i/H26K53U=": {
            "device_id": "9993",
            "device_name": "9993-agent",
            "device_public_ipv4": "73.5.6.4"
        }
    }
