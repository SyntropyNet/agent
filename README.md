[TOC]

---

#### [Latest SYNTROPY Agent Docs](https://docs.syntropystack.com/docs/start-syntropy-agent) 
- https://docs.syntropystack.com/docs/start-syntropy-agent
#### Prerequisites

* Wireguard kernel module is installed and loaded:
```bash
lsmod | grep wireguard
```

* Optional:  Docker is installed and running: 
```sh
docker system info
```
---
#### Limitations

* Docker network subnets can't overlap.
* 10.69.0.0/16 is used for internal Wireguard network

#### Steps
----
##### 1. Login to [https://platform.syntropystack.com](https://platform.syntropystack.com) 
---
##### 2. Create API key (Settings > API keys)

---

##### 3. Install SYNTROPY Agent

Possible Docker Container versions:

Stable:  ```syntropy/agent:stable```

Development:  ```syntropy/agent:devel``` or ```syntropy/agent:latest```  


###### With Docker 

```bash
docker run --network="host" --restart=on-failure:10 \ 
--cap-add=NET_ADMIN --cap-add=SYS_MODULE \
-v /var/run/docker.sock:/var/run/docker.sock:ro \
--device /dev/net/tun:/dev/net/tun \
--name=syntropy-agent \
-e SYNTROPY_API_KEY='z99CuiZnMhe2qtz4LLX43Gbho5Zu9G8oAoWRY68WdMTVB9GzuMY2HNn667A752EA' \
-e SYNTROPY_NETWORK_API='docker' \
-d syntropy/agent:stable
```
Check agent logs:

```docker logs syntropy-agent```

More information:     [https://docs.syntropystack.com/docs/start-syntropy-agent#install-with-docker](https://docs.syntropystack.com/docs/start-syntropy-agent#install-with-docker)

---


###### With Docker-compose


> With Portainer agent:

```bash
curl  https://raw.githubusercontent.com/SyntropyNet/syntropy-agent/master/docker-compose/na-pa.yml \
-o docker-compose.yaml
```

> Without portainer agent:

```bash
curl  https://raw.githubusercontent.com/SyntropyNet/syntropy-agent/master/docker-compose/syntropy-agent.yml \
-o docker-compose.yaml
```

Edit ```docker-compose.yaml``` file and edit these environment variables:

```yaml
SYNTROPY_API_KEY= your_api_key
```

Start containers:

```bash
docker-compose up -d
```

Check agent logs:
```bash
docker logs syntropy-agent
```

P.S. SYNTROPY Agent will ignore the default docker network, you will  need to create a separate network with different subnets on different hosts. Also, subnet 10.69.0.0/16 is used by our agent.

More information:

[https://docs.syntropystack.com/docs/start-syntropy-agent#install-as-docker-compose](https://docs.syntropystack.com/docs/start-syntropy-agent#install-as-docker-compose)

---


###### With pip 

```bash
pip3 install platform-agent
```

Download systemd service file:

```bash
curl https://raw.githubusercontent.com/SyntropyNet/syntropy-agent/master/systemd/syntropy-agent.service -o /etc/systemd/system/syntropy-agent.service
```

Create syntropy-agent directory:
```bash
mkdir /etc/systemd/system/syntropy-agent.service.d/
chmod -R 600 /etc/systemd/system/syntropy-agent.service.d/
```
Download settings file:
```bash
curl https://raw.githubusercontent.com/SyntropyNet/syntropy-agent/master/systemd/10-vars.conf -o /etc/systemd/system/syntropy-agent.service.d/10-vars.conf
```

Edit settings file ```/etc/systemd/system/syntropy-agent.service.d/10-vars.conf``` and change these settings:

```ini
[Service]
# Required parameters
Environment=SYNTROPY_API_KEY=YOUR_API_KEY
# Optional parameters
Environment=SYNTROPY_CONTROLLER_URL=controller-prod-platform-agents.syntropystack.com
Environment=SYNTROPY_ALLOWED_IPS=[{"10.0.44.0/24":"oracle_vpc"},{"192.168.111.2/32":"internal"}]
#If using docker , SYNTROPY_NETWORK_API=docker would allow agent to access docker networks for information.
Environment=SYNTROPY_NETWORK_API=none
Environment="SYNTROPY_AGENT_NAME=Azure EU gateway"

# Select one of providers from the list - https://docs.syntropystack.com/docs/start-syntropy-agent#section-variables
Environment="SYNTROPY_PROVIDER=1"

Environment=SYNTROPY_LAT=40.14
Environment=SYNTROPY_LON=-74.21
Environment=SYNTROPY_TAGS=Tag1,Tag2
Environment=SYNTROPY_SERVICES_STATUS=false
```

```bash
systemctl  daemon-reload
```

```bash
systemctl enable --now syntropy-agent
```

Check if service is running:
```bash
systemctl status syntropy-agent
```

More information: [https://docs.syntropystack.com/docs/start-syntropy-agent#install-with-pip](https://docs.syntropystack.com/docs/start-syntropy-agent#install-with-pip)

---