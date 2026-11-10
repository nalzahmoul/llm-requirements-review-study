# Step 6 - Analysis only: computes RQ1-RQ4 against the coding key and writes results/tests_output.txt.
# Needs final/final_codes.csv (made by step 5 after the consensus is done), the key in coding_key/
# and data/cases.csv. RQ3 compares explicit and implicit assumptions.
# How to run: open this file in VS Code and press Run (the triangle button).
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
code = subprocess.call([sys.executable, "runner/analyze.py"], cwd=PROJECT_FOLDER)
print("\nDone: see results/tests_output.txt" if code == 0 else "\nStopped - read the messages above")
sys.exit(code)
