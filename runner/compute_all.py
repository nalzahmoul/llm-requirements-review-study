#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheets import completeness, read_coder  # noqa: E402
from study import AGREEMENT, CODING, HERE, ROOT, ROUND, now_utc, sheet_name  # noqa: E402


def run(script, *args):
    print(f"\n----- {script} -----", flush=True)
    return subprocess.call([sys.executable, str(HERE / script), *args], cwd=ROOT)


def signature(a, b):
    """Fingerprint of the codes and extras (not of the file), so opening and saving in Excel changes nothing."""
    content = [[sorted((k[0], k[1], v["code"]) for k, v in c["codes"].items()),
                sorted((e["response_id"], e["statement"], e["cls"]) for e in c["extras"])] for c in (a, b)]
    return hashlib.sha256(json.dumps(content).encode()).hexdigest()


def main():
    pa, pb = CODING / sheet_name("A"), CODING / sheet_name("B")
    print(f"Coding round {ROUND}: {pa.name} + {pb.name} -> {AGREEMENT.name}/")
    missing = [p.name for p in (pa, pb) if not p.exists()]
    if missing:
        sys.exit(f"Put the sheets in {CODING} with these exact names: {', '.join(missing)}")
    a, b = read_coder(pa), read_coder(pb)
    problems = completeness(a, "A") + completeness(b, "B")
    if problems:
        print("The sheets are not complete yet:")
        for p in problems:
            print("  -", p)
        run("agreement.py", "--partial")
        print("\nProgress check only, nothing saved. Finish both sheets, then press again.")
        return 1

    state_file = AGREEMENT / "state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    sig = signature(a, b)
    if state.get("signature") != sig:
        if state:
            print("The codes in the sheets changed since the last agreement report, so it is measured again.")
        if run("agreement.py"):
            return 1
        AGREEMENT.mkdir(exist_ok=True)
        state_file.write_text(json.dumps(dict(signature=sig, measured=now_utc()), indent=1))
        print(f"\nNEXT: open {AGREEMENT.name}/consensus.xlsx together, settle every disagreement and every extra, "
              "save it, and press this button again.")
        return 0

    print(f"Agreement already measured on these codes ({state['measured']} UTC); see {AGREEMENT.name}/report_*.txt.")
    if run("finalize.py"):
        print(f"\nNEXT: fill in the open items in {AGREEMENT.name}/consensus.xlsx, save it, and press again.")
        return 1
    code = run("analyze.py")
    if code == 0:
        print("\nDONE: results/tests_output.txt has the statistical results.")
    return code


if __name__ == "__main__":
    sys.exit(main())
