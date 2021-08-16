import os
import logging
import socket
import requests

import docker
from requests.exceptions import ConnectionError, SSLError
from urllib3.exceptions import ProtocolError, NewConnectionError

from platform_agent.docker_api.helpers import format_networks_result, format_container_result
from platform_agent.config.settings import Config

logger = logging.getLogger()


def get_public_ip():
    try:
        return requests.get("https://ip.syntropystack.com/", timeout=2).json()
    except (NewConnectionError, SSLError, ConnectionError) as e:
        logger.warning(f"https://ip.syntropystack.com - could not be reached {e}")
        return requests.get('https://ident.me', timeout=5).text


def get_ip_addr():
    try:
        return {
            "external_ip": get_public_ip()
        }
    except (NewConnectionError, SSLError, ConnectionError) as e:
        logger.warning(f"https://ident.me - could not be reached {e}")
        return {}


def get_location():
    try:
        return {
            "location_lat": float(os.environ.get('SYNTROPY_LAT')),
            "location_lon": float(os.environ.get('SYNTROPY_LON')),
        }
    except ValueError:
        return {
            "location_lat": None,
            "location_lon": None
        }

def get_network_info():
    network_info = []
    if os.environ.get("SYNTROPY_NETWORK_API", '').lower() == "docker":
        try:
            docker_client = docker.from_env()
            networks = docker_client.networks()
            network_info = format_networks_result(networks)
        except (ProtocolError, ConnectionError):
            network_info = []
    network_info.extend(Config.get_valid_allowed_ips())
    return {
        "network_info": network_info
    }


def get_container_results():
    container_info = []
    if os.environ.get("SYNTROPY_NETWORK_API", '').lower() == "docker":
        try:
            docker_client = docker.from_env()
            networks = docker_client.containers()
            container_info = format_container_result(networks)
        except (ProtocolError, ConnectionError):
            container_info = []
    return {
        "container_info": container_info
    }


def get_srevice_status():
    if os.environ.get('SYNTROPY_SERVICES_STATUS') and os.environ.get('SYNTROPY_SERVICES_STATUS').lower() == 'true':
        return True
    else:
        return False


def get_provider():
    try:
        return int(os.environ['SYNTROPY_PROVIDER'])
    except (ValueError, KeyError):
        return None


def get_tags():
    tags = []
    for tag in Config.get_list_item('tags'):
        if len(tag) < 3:
            continue
        tags.append(tag)
    return tags


def get_info():
    return {
        "agent_name": os.environ.get('SYNTROPY_AGENT_NAME', socket.gethostname()),
        "agent_provider": get_provider(),
        "agent_category": os.environ.get('SYNTROPY_CATEGORY', None),
        "service_status": get_srevice_status(),
        "agent_tags": get_tags(),
        "network_ids": Config.get_list_item('network_ids'),
    }


def gather_initial_info():
    Config()
    result = {}
    result.update(get_ip_addr())
    result.update(get_network_info())
    result.update(get_info())
    result.update(get_container_results())
    result.update(get_location())
    return result
