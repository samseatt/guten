#!/usr/bin/env python3
"""Combine approved retention and monitoring into one guarded Admin CloudShell file."""
import argparse
from pathlib import Path
from prepare_backup_monitoring import launcher as monitoring,template
from prepare_backup_retention import launcher as retention


def combined(email):
    return ("#!/usr/bin/env python3\nimport sys\n"
            "def run_stage(source,name):\n"
            "    try:\n        exec(compile(source,name,'exec'), {})\n"
            "    except SystemExit as exc:\n        if exc.code not in (0,None): raise\n"
            "    except Exception as exc:\n        print(name+': '+str(exc),file=sys.stderr)\n        raise SystemExit(1) from None\n"
            'run_stage('+repr(retention())+', "retention setup")\n'
            'run_stage('+repr(monitoring(template(email)))+', "monitoring setup")\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--email',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.output.open('x') as stream:stream.write(combined(a.email))
    a.output.chmod(0o700)
