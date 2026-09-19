# Lightsail host software and container ingress

Both Guten hosts now have Docker Engine 29.8.1 and Compose 5.5.1 installed from Docker's signed Ubuntu repository. Package versions are pinned in `deploy/hosts/install-docker.sh` and recorded on each host at `/var/lib/guten/docker-packages.txt`. The installer refuses implicit upgrades and conflicting distribution packages. Docker access remains through sudo; no additional user was granted membership in the root-equivalent docker group.

This step created no additional AWS resources. Downloaded packages/images use existing host disk and network allowances. It did not import content, alter the Mac database, start PostgreSQL, change DNS, or deploy Guten applications.

## Repeatable installation

On a freshly bootstrapped Guten Ubuntu 24.04 amd64 host, transfer `deploy/hosts/install-docker.sh` and run it with `sudo sh`. It requires the `/etc/guten/host-role` marker installed by the infrastructure bootstrap. Review the script before running on any different host. Docker logs use the rotating `local` driver, limited to three 10 MB files per container (container-specific overrides can change that). Existing `/etc/docker/daemon.json` is not overwritten. OS-wide upgrades and reboots are separate maintenance operations.

Generate firewall commands locally, using the actual private addresses:

```bash
python3 scripts/configure_host_firewall.py --role database \
  --host-ip 172.26.4.118 --app-ip 172.26.5.8 \
  --output .cloud-provision/database-firewall.sh
python3 scripts/configure_host_firewall.py --role application \
  --host-ip 172.26.5.8 --app-ip 172.26.5.8 \
  --output .cloud-provision/application-firewall.sh
```

The generator refuses an existing output file. Transfer the matching generated file and `deploy/hosts/install-firewall.sh` to each host. Run `sudo sh install-firewall.sh < ROLE-firewall.sh`. It applies the rules and installs `/usr/local/lib/guten/firewall.sh` plus `/etc/systemd/system/docker.service.d/guten-firewall.conf`. Docker's ExecStartPre and ExecStartPost hooks reapply the rules before container restart and after daemon initialization. A firewall-hook failure fails Docker startup; inspect the journal rather than removing the guard.

Rules use iptables' DOCKER-USER chain and conntrack original destination, since Docker performs destination NAT before forwarding filters. Only the app host's private IPv4 may reach container-published database port 5432. The app host allows container-published TCP 80/443 only. Other new forwarded traffic arriving on ens5 is dropped; established return traffic and internally originating container traffic continue. Forwarded IPv6 ingress is denied. The dedicated chain is replaced atomically using iptables-restore without flushing unrelated chains. Reapplication does not duplicate jumps.

These are container-forwarding rules, not a complete host INPUT firewall. Host-native services, including SSH, remain governed by their own bindings and Lightsail's public firewall. Keep PostgreSQL containerized and bound to the private IPv4 only. Never rely on these rules to protect a new host-native database listener. Lightsail public ports remain app 80/443 and admin-/32 SSH, and database admin-/32 SSH only. Docker must retain its iptables firewall backend; review this integration before changing Docker networking/backend or the ens5 interface.

## Verification recorded September 18, 2026

- Both hosts ran a disposable hello-world container successfully.
- Both Docker services restarted successfully with the firewall hooks installed; their expected IPv4 and IPv6 chains remained present.
- Linux namespace tests exercised actual DNAT/forwarding with two source addresses and ports 5432, 8000, 80 and 443 for both host roles: 16 connection outcomes passed. Repeated rule installation also passed. This synthetic unauthorized-source test used isolated Linux namespaces; it did not create a third AWS instance.
- A temporary Docker HTTP listener on the database host's private ports 5432 and 8000 was probed from the actual app host. Port 5432 connected, and 8000 was blocked. The listener was removed immediately afterward.
- Portable input-validation/shell tests passed. IPv6 rules were installed and inspected, but IPv6 packet behavior and a full host reboot have not been separately rehearsed.

The namespace test is retained as `scripts/test_host_firewall_linux.py`, importing the sibling firewall generator. Run with root on Linux. It creates uniquely named isolated networks, starts a tiny Python socket listener, verifies packet outcomes, and cleans up processes/namespaces in a finally block. It does not edit the real host firewall. Portable tests: `python3 -m unittest discover -s tests -p test_host_firewall.py`.

Installation and live verification logs are ignored local operational artifacts under `.cloud-provision/` (`docker-install-*.log`, `host-verify-*.log`, `firewall-packet-tests.log`, `private-network-test.log`). The SSH keys there must remain private and outside Git.

## Next deployment checkpoint

Build the prepared PostgreSQL 17 image, generate host-specific TLS/credentials with the offline CA kept on the Mac, and start an empty cluster on its dedicated external volume. Then import a fresh verified Guten dump into a new staging database, validate content and migration state, and establish backup encryption/upload/recovery before application cutover. S3 configuration inspection, scoped upload credentials, backup alerts and retention are still pending. See [cloud-database.md](cloud-database.md).

Sources: [Docker Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/), [Docker packet filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
