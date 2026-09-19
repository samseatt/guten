#!/usr/bin/env python3
"""Root-only isolated Linux network-namespace packet tests; no real host firewall edits."""
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
from configure_host_firewall import render


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root on Linux')
    tag = 'gt' + uuid.uuid4().hex[:6]
    client, router, server = [tag + suffix for suffix in ('c','r','s')]
    namespaces = []
    processes = []
    def ns(name, *args, **kwargs):
        return run('ip', 'netns', 'exec', name, *args, **kwargs)
    try:
        for name in (client,router,server):
            run('ip','netns','add',name)
            namespaces.append(name)
            ns(name,'ip','link','set','lo','up')
        for a,b,left,right in [('gc','ens5',client,router),('gb','gs',router,server)]:
            run('ip','link','add',a,'netns',left,'type','veth','peer','name',b,'netns',right)
            ns(left,'ip','link','set',a,'up')
            ns(right,'ip','link','set',b,'up')
        for name,dev,addr in [(client,'gc','10.10.0.2/24'),(client,'gc','10.10.0.3/24'),(router,'ens5','10.10.0.1/24'),(router,'gb','10.20.0.1/24'),(server,'gs','10.20.0.2/24')]:
            ns(name,'ip','addr','add',addr,'dev',dev)
        ns(server,'ip','route','add','default','via','10.20.0.1')
        ns(router,'sysctl','-w','net.ipv4.ip_forward=1')
        # DNAT matches Docker's forwarding path: the rule must inspect original destination.
        for port in (5432,8000,80,443):
            ns(router,'iptables','-t','nat','-A','PREROUTING','-d','10.10.0.1','-p','tcp','--dport',str(port),'-j','DNAT','--to-destination','10.20.0.2:9000')
        with tempfile.TemporaryDirectory() as directory:
            ready=Path(directory)/'ready'
            code="import socket,pathlib; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('10.20.0.2',9000)); s.listen(); pathlib.Path("+repr(str(ready))+").touch(); exec('while True:\\n c,a=s.accept(); c.sendall(b\"ok\"); c.close()')"
            processes.append(subprocess.Popen(['ip','netns','exec',server,'python3','-c',code]))
            import time
            for _ in range(100):
                if ready.exists(): break
                time.sleep(.02)
            assert ready.exists(), 'Listener did not start'
            def probe(source,port,allowed):
                code=f"import socket; s=socket.socket(); s.settimeout(0.5); s.bind(('{source}',0)); s.connect(('10.10.0.1',{port})); assert s.recv(2)==b'ok'"
                result=subprocess.run(['ip','netns','exec',client,'python3','-c',code],capture_output=True)
                assert (result.returncode==0)==allowed, (source,port,allowed,result.stderr)
            for role in ('database','application'):
                script=render(role,'10.10.0.1','10.10.0.2')
                ns(router,'sh',input=script)
                ns(router,'sh',input=script)  # reapplication must preserve behavior
                for source in ('10.10.0.2','10.10.0.3'):
                    for port in (5432,8000,80,443):
                        allowed=(source=='10.10.0.2' and port==5432) if role=='database' else port in (80,443)
                        probe(source,port,allowed)
                print(role+': packet allow/deny and idempotency passed',flush=True)
    finally:
        for process in processes:
            process.terminate()
            process.wait()
        for name in reversed(namespaces):
            run('ip','netns','delete',name)

if __name__ == '__main__':
    main()
