import json

from platform_agent.config.settings import AGENT_PATH_TMP


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


def update_tmp_file(data, file_name):
    iface_info_path = f"{AGENT_PATH_TMP}/{file_name}"
    with open(iface_info_path, 'w+') as file:
        json.dump(data, file, indent=4)
        file.close()


def update_tmp_config_dump(cmd, file_name="config_dump"):
    data = read_tmp_file(file_name)
    cmds = data.get('vpn', [])
    cmds.append(cmd)
    data['vpn'] = cmds
    update_tmp_file(data, file_name)


def get_peer_metadata(file_name="config_dump"):
    data = read_tmp_file(file_name)
    cmds = data.get('vpn', [])
    peer_metadata = {}
    for cmd in cmds:
        if cmd['fn'] != 'add_peer':
            continue
        peer_metadata[cmd['args']['public_key']] = cmd['metadata']
    return peer_metadata
