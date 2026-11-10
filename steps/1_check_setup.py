# Step 1 - Check the key and model IDs: one tiny test request to each of the 3 models (under one cent).
# Every line should say OK. Paste your OpenRouter key into runner/keys.env first.
# How to run: open this file in VS Code and press Run (the triangle button).
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
code = 0
for cmd in [['runner/run_reviews.py', '--check']]:
    code = subprocess.call([sys.executable] + cmd, cwd=PROJECT_FOLDER)
    if code:
        break
print("\nDone." if code == 0 else "\nStopped - read the messages above")
sys.exit(code)
