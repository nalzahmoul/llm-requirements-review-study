# Step 2 - Prepare the data: the 132 interview-requirement pairs of the 11 Ski interviews.
# Writes data/cases.csv and data/transcripts_manifest.csv, and checks the counts (72 / 22 / 38).
# How to run: open this file in VS Code and press Run (the triangle button).
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
code = 0
for cmd in [['runner/prepare_data.py']]:
    code = subprocess.call([sys.executable] + cmd, cwd=PROJECT_FOLDER)
    if code:
        break
print("\nDone." if code == 0 else "\nStopped - read the messages above")
sys.exit(code)
