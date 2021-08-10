import subprocess

from pyroute2 import IPDB


def get_default_iface_name():
    ip = IPDB()
    interface_name = ip.interfaces[ip.routes['default']['oif']].get('ifname')
    ip.release()
    return interface_name


def iptables_version():
    iptables_proc = subprocess.Popen(['iptables', '-L'], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
    text = iptables_proc.stderr.read()
    if "Warning: iptables-legacy tables present, use iptables-legacy to see them" in str(text):
        return 'iptables-nft'
    else:
        return 'iptables'


def iptables_create_syntropy_chain(version='-nft'):
    try:
        # Check if already exists, if not - create
        subprocess.run([f'iptables{version}', '-N', 'SYNTROPY_CHAIN'], stderr=subprocess.DEVNULL)
        subprocess.run(
            [f'iptables{version}', '-C', 'FORWARD', '-s', '0.0.0.0/0', '-d', '0.0.0.0/0', '-j', 'SYNTROPY_CHAIN'],
            check=True,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            [f'iptables{version}', '-I', 'FORWARD', '-s', '0.0.0.0/0', '-d', '0.0.0.0/0', '-j', 'SYNTROPY_CHAIN'],
            stderr=subprocess.DEVNULL,
            check=False
        )
    if version == '-nft':
        iptables_create_syntropy_chain(version='-legacy')


def add_iptable_rules(ips: list, version='-nft'):
    for ip in ips:
        try:
            # Check if already exists, if not - create
            subprocess.run(
                [f'iptables{version}', '-C', 'SYNTROPY_CHAIN', '-p', 'all', '-s', ip, '-j', 'ACCEPT'],
                check=True,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            subprocess.run(
                [f'iptables{version}', '-A', 'SYNTROPY_CHAIN', '-p', 'all', '-s', ip, '-j', 'ACCEPT'],
                check=False,
                stderr=subprocess.DEVNULL
            )
    if version == '-nft':
        add_iptable_rules(ips, version='-legacy')


def delete_iptable_rules(ips: list, chain='SYNTROPY_CHAIN', version='-nft'):
    for ip in ips:
        subprocess.run(
            [f'iptables{version}', '-D', chain, '-p', 'all', '-s', ip, '-j', 'ACCEPT'],
            check=False,
            stderr=subprocess.DEVNULL
        )
    if version == '-nft':
        delete_iptable_rules(ips, version='-legacy')


def add_iptables_forward(ifname, version='-nft'):
    try:
        # Check if already exists, if not - create
        subprocess.run(
            [f'iptables{version}', '-C', 'FORWARD', '-i', ifname, '-j', 'ACCEPT'],
            check=True,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            [f'iptables{version}', '-A', 'FORWARD', '-i', ifname, '-j', 'ACCEPT'],
            check=False,
            stderr=subprocess.DEVNULL
        )
        if "PUBLIC" in ifname:
            subprocess.run(
                [f'iptables{version}', '-t', 'nat', '-A', 'POSTROUTING', '-o', get_default_iface_name(), '-j', 'MASQUERADE'],
                check=False,
                stderr=subprocess.DEVNULL
            )
    if version == '-nft':
        add_iptables_forward(ifname, version='-legacy')
