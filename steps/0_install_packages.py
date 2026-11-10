# Step 0 - Install the Python packages the scripts need (once).

# How to run: open this file in VS Code and press Run (the triangle button).
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
code = 0
for cmd in [['-m', 'pip', 'install', '-r', 'runner/requirements.txt']]:
    code = subprocess.call([sys.executable] + cmd, cwd=PROJECT_FOLDER)
    if code:
        break
print("\nDone." if code == 0 else "\nStopped - read the messages above")
sys.exit(code)
