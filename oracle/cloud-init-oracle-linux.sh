#!/bin/bash
sudo yum update -y
sudo yum install python3-pip -y
sudo pip3 install platform-agent-devel
sudo yum install https://www.elrepo.org/elrepo-release-7.el7.elrepo.noarch.rpm -y
sudo yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm -y
sudo yum install yum-plugin-elrepo wireguard-tools -y
sudo yum --enablerepo=elrepo-kernel install kernel-ml -y
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
sudo grub2-set-default 0
sudo setenforce 0
sudo touch /etc/modules-load.d/wireguard.conf
sudo echo wireguard >> /etc/modules-load.d/wireguard.conf
sudo curl https://bitbucket.org/syntropynetwork-team/platform-agent/raw/master/systemd/syntropy-agent.service \
-o /etc/systemd/system/syntropy-agent.service
sudo mkdir /etc/systemd/system/syntropy-agent.service.d/
sudo echo [Service] >> /etc/systemd/system/syntropy-agent.service.d/10-vars.conf
sudo echo Environment=SYNTROPY_API_KEY=CHANGE_ME >> /etc/systemd/system/syntropy-agent.service.d/10-vars.conf
sudo systemctl daemon-reload
sudo systemctl enable syntropy-agent
sudo firewall-cmd --permanent --zone=public --add-port=1024-65535/udp
sudo reboot

