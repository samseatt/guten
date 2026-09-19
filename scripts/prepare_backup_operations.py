#!/usr/bin/env python3
"""Combine approved retention and monitoring into one guarded Admin CloudShell file."""
import argparse
from pathlib import Path
from prepare_backup_monitoring import launcher as monitoring,template
from prepare_backup_retention import launcher as retention


def combined(email):
    return ('#!/usr/bin/env python3\n'
            '# Update only backup lifecycle, then create the small monitoring stack.\n'
            'try:\n    exec('+repr(retention())+', {})\n'
            'except SystemExit as exc:\n    if exc.code not in (0,None): raise\n'
            'exec('+repr(monitoring(template(email)))+', {})\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--email',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.output.open('x') as stream:stream.write(combined(a.email))
    a.output.chmod(0o700)
