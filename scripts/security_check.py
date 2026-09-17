"""Record dependency audit reports without installing or updating applications."""
import os
from pathlib import Path
import subprocess
import time
import sys
ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "artifacts" / ("security_" + time.strftime("%Y%m%dT%H%M%S"))
output.mkdir(parents=True, exist_ok=True)
failed = False
for name in ("guten", "guten-crust", "guten-portal", "guten-sites"):
    result = subprocess.run(["npm", "audit", "--json"], cwd=ROOT.parent/name, capture_output=True, text=True)
    (output/(name+".json")).write_text(result.stdout)
    if result.stderr: (output/(name+".stderr.log")).write_text(result.stderr)
    print(name + (": PASS" if result.returncode == 0 else ": FAILED (see report)"))
    failed |= result.returncode != 0
python = os.environ.get("SECURITY_PYTHON") or sys.executable
result = subprocess.run([python, "-m", "pip_audit", "-r", str(ROOT.parent/"guten-datalake/requirements.txt"), "--no-deps", "--disable-pip", "--format", "json"],capture_output=True,text=True)
(output/"guten-datalake.json").write_text(result.stdout)
(output/"guten-datalake.stderr.log").write_text(result.stderr)
failed |= result.returncode != 0
print("guten-datalake" + (": PASS" if result.returncode == 0 else ": FAILED (install audit tooling or inspect report)"))
print("Reports:", output)
raise SystemExit(1 if failed else 0)
