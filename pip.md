# Manual
You can install NOIA using pip. If you don’t have pip installed, you can download it from here.
Pip is the package installer for Python. You can use pip to install packages from the Python Package Index and other indexes. https://pypi.org/project/pip/
#### 1. Install NOIA agent
`pip3 install platform-agent`
#### 2. Create/Edit /etc/systemd/system/noia-agent.service.d/10-vars.conf file 
##### NOIA_API_KEY (Required)

```ini
[Service]
# Required parameters

Environment = NOIA_API_KEY=YOUR_API_KEY

# Optional parameters

Environment = NOIA_CONTROLLER_URL = app-controller-platform-agents.noia.network
Environment = NOIA_ALLOWED_IPS = [{"10.0.44.0/24":"oracle_vpc"},{"192.168.111.2/32":"internal"}]

# If using docker , NOIA_NETWORK_API = docker would allow agent to access docker networks for information.

Environment = NOIA_NETWORK_API = none

Environment = NOIA_NAME = Azure EU gateway

Environment = NOIA_COUNTRY = Germany

Environment = NOIA_CITY = Frankfurt

# Select one of the categories from the list or default will be assigned
# 'IoT','Server','none'

Environment = NOIA_CATEGORY = IoT

# Select one of providers from the list or default will be assigned
# 'AWS', 'DigitalOcean', 'Microsoft Azure', 'Rackspace', 'Alibaba Cloud',
# 'Google Cloud Platform', 'Oracle Cloud', 'VMware', 'IBM Cloud', 'Vultr'.

Environment = NOIA_PROVIDER = Microsoft Azure
Environment = NOIA_LAT = 40.14
Environment = NOIA_LON = -74.21

```
### Create Systemd service


```ini

[Unit]
	
Description = NOIA Platform Agent
After = multi-user.target

[Service]
	
Type = simple
Restart = always
RestartSec = 1
ExecStart = /usr/local/bin/noia_agent run

[Install]
	
WantedBy = multi-user.target

```
