"""Launch the project supervisor outside a temporary Windows tool job."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
logs = root / "artifacts/runtime"
logs.mkdir(parents=True, exist_ok=True)
with (logs / "supervisor.log").open("ab", buffering=0) as output:
    # Fail clearly if breakaway is denied; do not recreate the temporary-job outage.
    child = subprocess.Popen([sys.argv[1], str(root / "scripts/supervisor.mjs")],
        cwd=root, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_BREAKAWAY_FROM_JOB)
    print(child.pid)
