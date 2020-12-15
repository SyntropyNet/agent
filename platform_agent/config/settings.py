import os
import ipaddress
import json
from pathlib import Path

import yaml

CONFIG_FILE = "/etc/syntropy-agent/config.yaml"

AGENT_PATH = "/etc/syntropy-agent"
AGENT_PATH_TMP = f"{AGENT_PATH}/tmp"

class ConfigException(Exception):
    pass


class Config:

    _data = None

    def __init__(self):

        agent_dir = Path(AGENT_PATH)
        if not agent_dir.is_dir():
            agent_dir.mkdir()
            agent_dir.chmod(0o700)
        tmp_dir = Path(AGENT_PATH_TMP)
        if not tmp_dir.is_dir():
            tmp_dir.mkdir()
            tmp_dir.chmod(0o700)
        if os.environ.get("SYNTROPY_NETWORK_API", '').lower() == "kubernetes" and not os.environ.get('SYNTROPY_AGENT_NAME'):
            try:
                os.environ['SYNTROPY_AGENT_NAME'] = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()
            except FileNotFoundError:
                pass
        if os.environ.get("SYNTROPY_API_KEY"):
            return
        if os.environ.get("SYNTROPY_LOG_LEVEL"):
            if os.environ["SYNTROPY_LOG_LEVEL"].upper() in ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                os.environ["SYNTROPY_LOG_LEVEL"] = os.environ["SYNTROPY_LOG_LEVEL"].upper()
            elif not (os.environ["SYNTROPY_LOG_LEVEL"].isdigit() and os.environ["SYNTROPY_LOG_LEVEL"] in ['0', '10', '20', '30', '40', '50']):
                os.environ["SYNTROPY_LOG_LEVEL"] = '20'
        else:
            os.environ["SYNTROPY_LOG_LEVEL"] = '20'

        if os.environ.get('SYNTROPY_USER_API') == 'DOCKER' and not os.environ.get('SYNTROPY_DOCKER_URL'):
            raise ConfigException(f"For Docker API, you must provide SYNTROPY_DOCKER_URL")

        config_file = Path(CONFIG_FILE)
        if not config_file.is_file():
            print(f"Config file was not found in {CONFIG_FILE}")
            raise ConfigException(f"Config file was not found in {CONFIG_FILE}")
        env_conf = self.get_config()
        if env_conf.get('name') and type(env_conf['name']) == str:
            os.environ[f"SYNTROPY_AGENT_NAME"] = env_conf['name']
        for k, v in env_conf.get('connection', {}).items():
            if type(v) in [int, str]:
                os.environ[f"SYNTROPY_{k.upper()}"] = str(v)

    @staticmethod
    def get_config():
        try:
            with open(CONFIG_FILE) as f:
                config_dict = yaml.safe_load(f)
                return config_dict
        except FileNotFoundError:
            return {}

    @staticmethod
    def get_list_item(key: str):
        if os.environ.get(f'SYNTROPY_{key.upper()}'):
            result = os.environ.get(f'SYNTROPY_{key.upper()}').split(',')
            return result
        result = Config.get_config().get(key, [])
        if type(result) != list:
            result = []
        return result


    @staticmethod
    def get_valid_allowed_ips():

        def update_results(result: list, subnet: str, subnet_name: str):
            try:
                ip_network = ipaddress.ip_interface(subnet)
            except ValueError:
                return result
            result.append(
                {
                    'agent_network_name': subnet_name,
                    'agent_network_subnets': [ip_network.with_prefixlen]
                }
            )
            return result

        results = []
        if os.environ.get('SYNTROPY_ALLOWED_IPS'):
            try:
                allowed_ips = json.loads(os.environ['SYNTROPY_ALLOWED_IPS'])
            except json.JSONDecodeError:
                return []
            for allowed_ip in allowed_ips:
                for k, v in allowed_ip.items():
                    if not (type(k) == type(v) == str):
                        continue
                    update_results(results, k, v)
            return results
        allowed_ips = Config.get_config().get('allowed_ips', [])
        for allowed_ip in allowed_ips:
            if allowed_ip.get('name') and allowed_ip.get('subnet'):
                try:
                    ip_network = ipaddress.ip_interface(allowed_ip['subnet'])
                except ValueError:
                    continue
                results = update_results(results, ip_network.with_prefixlen, allowed_ip['name'])
        return results
