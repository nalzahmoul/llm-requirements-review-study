# Step 3 - Collect the responses: 3 models x 11 transcripts = 33 into responses/.
# Safe to re-run: only missing, failed or cut-off requests are sent again. Re-run until it says 33 of 33.
# How to run: open this file in VS Code and press Run (the triangle button).
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
code = 0
for cmd in [['runner/run_reviews.py']]:
    code = subprocess.call([sys.executable] + cmd, cwd=PROJECT_FOLDER)
    if code:
        break
print("\nDone." if code == 0 else "\nStopped - read the messages above")
sys.exit(code)
