import docker


def format_networks_result(networks):
    result = []
    for network in networks:
        subnets = []
        for subnet in network['IPAM']['Config']:
            subnets.append(subnet['Subnet'])
        if subnets:
            result.append(
                {
                    'agent_network_id': network['Id'],
                    'agent_network_name': network.get('Name'),
                    'agent_network_subnets': subnets,
                }
            )
    return result


def format_container_result(containers):
    docker_client = docker.from_env()
    networks = docker_client.networks()
    conts = {}
    for network in networks:
        for k, v in network['Containers'].items():
            if not v['IPv4Address']:
                continue
            if conts.get(k) and conts[k]['IPv4Address'] != v['IPv4Address']:
                conts[k]['IPv4Address'].append(v['IPv4Address'].split('/')[0])
                conts[k]['network_names'].append(network['Name'])
                continue
            conts[k] = v
            conts[k]['IPv4Address'] = [conts[k].get('IPv4Address').split('/')[0]]
            conts[k]['network_names'] = [network.get('Name')]
    result = []
    for container in containers:
        ports = {'udp': [], 'tcp': []}
        for port in container.get('Ports', []):
            private_port = port.get('PrivatePort')
            public_port = port.get('PublicPort')
            port_type = port.get('Type')
            if not port_type:
                continue
            if private_port and private_port not in ports[port_type]:
                ports[port_type].append(private_port)
            if public_port and public_port not in ports[port_type]:
                ports[port_type].append(public_port)
        container_info = conts.get(container['Id'])

        if container_info:

            container_conf = docker_client.inspect_container(container['Id'])['Config']

            try:
                container_info['name'] = \
                    [name for name in container_conf.get('Env', []) if 'SYNTROPY_SERVICE_NAME' in name][0].split('=')[1]
            except IndexError:
                container_info['name'] = container_conf.get('Domainname', container_info.get('Name'))

            result.append(
                {
                    'agent_container_id': container['Id'],
                    'agent_container_name': container_info.get('name'),
                    'agent_container_ips': container_info.get('IPv4Address'),
                    'agent_container_networks': container_info.get('network_names'),
                    'agent_container_ports': ports,
                    'agent_container_state': container.get('State'),
                    'agent_container_uptime': container.get('Status'),
                }
            )
    return result
