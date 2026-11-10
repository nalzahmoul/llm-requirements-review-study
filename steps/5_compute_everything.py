# Step 5 - When both finish, put BOTH filled sheets in coding/ and press Run.
# Round 1: coding_sheet_coderA.xlsx + coding_sheet_coderB.xlsx (results in agreement/).
# Round 2: coding_sheet_coderA-2.xlsx + coding_sheet_coderB-2.xlsx (results in agreement_round2/).
# Which round is computed is set by ROUND in runner/study.py (now 2).
# Each press does the next thing: agreement report (kappa, alpha) -> you settle agreement/consensus.xlsx ->
# press again -> final codes + the full analysis in results/summary.txt. 
# How to run: open this file in VS Code and press Run (the triangle button).
import subprocess
import sys
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent.parent
code = 0
for cmd in [['runner/compute_all.py']]:
    code = subprocess.call([sys.executable] + cmd, cwd=PROJECT_FOLDER)
    if code:
        break
print("\nDone." if code == 0 else "\nStopped - read the messages above")
sys.exit(code)
