import logging
import json
import os

from platform_agent.config.settings import AGENT_PATH_TMP
logger = logging.getLogger()


def check_if_file_exist(file_name):
    return os.path.isfile(f"{AGENT_PATH_TMP}/{file_name}")


def update_file(file_name, data):
    file_path = f"{AGENT_PATH_TMP}/{file_name}"
    with open(file_path, 'w+') as file_path:
        json.dump(data, file_path, indent=4)
        file_path.close()


def read_tmp_file(file_name='iface_info'):
    """Read file"""
    try:
        with open(f"{AGENT_PATH_TMP}/{file_name}") as json_file:
            rez = json_file.read()
            try:
                data = json.loads(rez)
            except json.JSONDecodeError:
                data = {}
    except FileNotFoundError:
        data = {}
    return data


def format_results_for_controller(peer_info):
    result = []
    for iface in peer_info.keys():
        result.append(
            {
                "iface": iface,
                "iface_public_key": peer_info[iface]['iface_public_key'],
                "peers": list(peer_info[iface]['peers'].values())
            }
        )
    return result