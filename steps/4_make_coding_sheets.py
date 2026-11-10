# Step 4 - Blinded coding sheets for BOTH authors, all 33 responses (396 rows each), into coding/.
# Give coding/ to Partner (use coding_sheet_coderB.xlsx). Do not open coding_key/ until consensus is done.
# How to run: open this file in VS Code and press Run (the triangle button).
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
code = 0
for cmd in [['runner/make_coding_sheets.py']]:
    code = subprocess.call([sys.executable] + cmd, cwd=PROJECT_FOLDER)
    if code:
        break
print("\nDone." if code == 0 else "\nStopped - read the messages above")
sys.exit(code)
