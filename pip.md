# Manual
You can install SYNTROPY using pip. If you don't have pip installed, you can download it from here.
Pip is the package installer for Python. You can use pip to install packages from the Python Package Index and other indexes. https://pypi.org/project/pip/
#### 1. Install SYNTROPY agent
`pip3 install platform-agent`
#### 2. Create/Edit /etc/systemd/system/syntropy-agent.service.d/10-vars.conf file 
##### SYNTROPY_API_KEY (Required)
```ini
[Service]

# Required parameters

Environment=SYNTROPY_API_KEY=YOUR_API_KEY

# Optional parameters

Environment=SYNTROPY_CONTROLLER_URL=controller-prod-platform-agents.syntropystack.com
Environment=SYNTROPY_ALLOWED_IPS=[{"10.0.44.0/24":"oracle_vpc"},{"192.168.111.2/32":"internal"}]

# If using docker , SYNTROPY_NETWORK_API=docker would allow agent to access docker networks for information.

Environment=SYNTROPY_NETWORK_API=none

Environment=SYNTROPY_AGENT_NAME=Azure EU gateway

# Select one of providers from the list - https://docs.syntropystack.com/docs/start-syntropy-agent#section-variables

Environment=SYNTROPY_PROVIDER=1

Environment=SYNTROPY_LAT=40.14
Environment=SYNTROPY_LON=-74.21

Environment=SYNTROPY_SERVICES_STATUS=false
```
### Create Systemd service

```ini
[Unit]
Description=SYNTROPY Platform Agent
After=multi-user.target

[Service]
Type=simple
Restart=always
RestartSec=1
ExecStart=/usr/local/bin/syntropy_agent run

[Install]
WantedBy=multi-user.target

```
