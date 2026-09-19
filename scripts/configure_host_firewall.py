#!/usr/bin/env python3
"""Generate Docker-aware ingress guards for Guten hosts; makes no remote changes."""
import argparse
import ipaddress
from pathlib import Path


def render(role, host_ip, app_ip, interface='ens5'):
    for value in (host_ip, app_ip):
        address = ipaddress.IPv4Address(value)
        if not address.is_private or address.is_loopback or address.is_unspecified:
            raise ValueError('Private host IPv4 addresses required')
    if role not in ('application', 'database') or interface != 'ens5':
        raise ValueError('Expected known Guten role and ens5 interface')
    rules = [
        '*filter', ':GUTEN-INGRESS - [0:0]', '-F GUTEN-INGRESS',
        '-A GUTEN-INGRESS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN',
    ]
    if role == 'database':
        rules.append(f'-A GUTEN-INGRESS -i {interface} -s {app_ip}/32 -p tcp -m conntrack --ctorigdst {host_ip} --ctorigdstport 5432 -j RETURN')
    else:
        for port in (80, 443):
            rules.append(f'-A GUTEN-INGRESS -i {interface} -p tcp -m conntrack --ctorigdst {host_ip} --ctorigdstport {port} -j RETURN')
    rules += [f'-A GUTEN-INGRESS -i {interface} -j DROP', '-A GUTEN-INGRESS -j RETURN', 'COMMIT']
    ipv6 = '\n'.join([
        '*filter', ':GUTEN-INGRESS - [0:0]', '-F GUTEN-INGRESS',
        '-A GUTEN-INGRESS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN',
        f'-A GUTEN-INGRESS -i {interface} -j DROP', '-A GUTEN-INGRESS -j RETURN', 'COMMIT',
    ])
    return """#!/bin/sh
set -eu
# Installed as Docker ExecStartPre/Post: guard before containers start and recheck after.
# No host INPUT/SSH changes. Only forwarded container ingress is restricted.
iptables -w -N DOCKER-USER 2>/dev/null || iptables -w -S DOCKER-USER >/dev/null
iptables-restore --wait --noflush <<'RULES'
""" + '\n'.join(rules) + """
RULES
iptables -w -C DOCKER-USER -j GUTEN-INGRESS 2>/dev/null || iptables -w -I DOCKER-USER 1 -j GUTEN-INGRESS
iptables -w -C FORWARD -j DOCKER-USER 2>/dev/null || iptables -w -I FORWARD 1 -j DOCKER-USER
ip6tables-restore --wait --noflush <<'RULES'
""" + ipv6 + """
RULES
ip6tables -w -C FORWARD -j GUTEN-INGRESS 2>/dev/null || ip6tables -w -I FORWARD 1 -j GUTEN-INGRESS
"""


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--role', choices=['application', 'database'], required=True)
    p.add_argument('--host-ip', required=True)
    p.add_argument('--app-ip', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    content = render(a.role, a.host_ip, a.app_ip)
    with a.output.open('x') as stream:
        stream.write(content)
    a.output.chmod(0o700)
