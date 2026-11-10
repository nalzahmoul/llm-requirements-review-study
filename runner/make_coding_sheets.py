#!/usr/bin/env python3

import argparse
import csv
import random
import shutil
import sys
from collections import Counter
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from study import (CODEBOOK, CODES, CODING, CODING_STEPS, EXTRA_CLASSES, EXTRAS_STEP, KEY_DIR,  # noqa: E402
                   RESPONSES, TRANSCRIPTS, load_records, read_cases, read_include, requirements_by_transcript)

KEY_NAME = "KEY_do_not_open_until_consensus_is_done.csv"
HEAD = ["row_id", "response_id", "transcript_file", "req_id", "requirement (LLMREI wording)",
        "code", "evidence (quote from the response)", "notes"]
EXTRA_HEAD = ["response_id", "extra statement (quote or first words)", "class (Supported/Unsupported)",
              "transcript evidence (if Supported)", "notes"]
RESP_HEAD = ["response_id", "transcript_file", "extras_checked (Y)", "notes"]
EXTRA_ROWS = 1500  # empty rows prepared with drop-down lists


def write_codebook_html(path):
    colors = {"Supports": "#2E7D32", "Asks": "#1F5FAD", "Assumes explicitly": "#D46A00",
              "Assumes implicitly": "#C62828", "Omits": "#6B6B6B"}
    e = escape
    codes = "".join(f'<tr><td><b style="color:{colors[n]}">{e(n)}</b></td><td>{e(d)}</td><td>{e(r)}</td></tr>'
                    for n, d, r in CODEBOOK if n in CODES)
    special = "".join(f"<tr><td><b>{e(n)}</b></td><td>{e(d)}</td><td>{e(r)}</td></tr>"
                      for n, d, r in CODEBOOK if n not in CODES)
    steps = "".join(f"<li><b>{e(f)}</b>: {e(t)}</li>" for f, t in CODING_STEPS)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Codebook</title>
<style>body{{font:14px/1.45 Georgia,serif;max-width:900px;margin:24px auto;padding:0 16px;color:#111;background:#fff}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:16px;margin:22px 0 6px;color:#1F5FAD}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #bbb;padding:6px 8px;vertical-align:top;text-align:left}}
th{{background:#eef3fb}}td:first-child{{width:150px}}.note{{color:#555;font-size:13px}}</style></head><body>
<h1>Codebook: Ask or Assume? (MO2RE 2027)</h1>
<p class="note">Both authors code all 33 responses independently with this codebook. It is generated from
runner/study.py; change rules only there.</p>
<h2>1. What you code</h2>
<p>For each response you have the interview transcript (coding/transcripts), the 12 predefined requirements of the
Ski scenario, and the response (coding/blinded_responses/RSPxxx.txt). Code every predefined requirement once per
response, then list the response's extras.</p>
<h2>2. The five codes</h2>
<table><tr><th>Code</th><th>Definition</th><th>Rule</th></tr>{codes}</table>
<h2>3. Special cases</h2>
<table><tr><th>Case</th><th>When</th><th>Rule</th></tr>{special}</table>
<h2>4. What to fill in for each requirement</h2><ul>{steps}</ul>
<h2>5. Once per response: extras</h2><p>{e(EXTRAS_STEP)}</p>
<h2>6. Blinding</h2>
<p>Code alone. Until both sheets are complete, do not open the coding_key folder, data/cases.csv,
data/all_cases.csv, the responses folder or the other author's sheet.</p>
</body></html>"""
    Path(path).write_text(page, encoding="utf-8")


def build_workbook(path, coder, rows, response_rows):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    grey, bold = PatternFill("solid", fgColor="E7E6E6"), Font(bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")
    rsp_list = '"' + ",".join(r[0] for r in response_rows) + '"'

    ws = wb.active
    ws.title = "Coding"
    ws.append(HEAD)
    for r in rows:
        ws.append(r + [None] * (len(HEAD) - len(r)))
    n = len(rows) + 1
    for c in ws[1]:
        c.font = bold
    for row in ws.iter_rows(min_row=2, max_row=n, max_col=5):
        for c in row:
            c.fill, c.alignment = grey, wrap
    for col, w in zip("ABCDEFGH", [9, 11, 44, 7, 55, 18, 50, 25]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "F2"
    dv = DataValidation(type="list", formula1='"' + ",".join(CODES) + '"', allow_blank=True,
                        showErrorMessage=True, errorTitle="Not a code", error="Choose one of the five codes.")
    dv.add(f"F2:F{n}")
    ws.add_data_validation(dv)

    ex = wb.create_sheet("Extras")
    ex.append(EXTRA_HEAD)
    for c in ex[1]:
        c.font, c.alignment = bold, wrap
    for col, w in zip("ABCDE", [11, 60, 16, 45, 25]):
        ex.column_dimensions[col].width = w
    ex.freeze_panes = "A2"
    dv_r = DataValidation(type="list", formula1=rsp_list, allow_blank=True)
    dv_r.add(f"A2:A{EXTRA_ROWS + 1}")
    dv_c = DataValidation(type="list", formula1='"' + ",".join(EXTRA_CLASSES) + '"', allow_blank=True)
    dv_c.add(f"C2:C{EXTRA_ROWS + 1}")
    ex.add_data_validation(dv_r)
    ex.add_data_validation(dv_c)

    rs = wb.create_sheet("Responses")
    rs.append(RESP_HEAD)
    for r in response_rows:
        rs.append(list(r))
    for c in rs[1]:
        c.font = bold
    for row in rs.iter_rows(min_row=2, max_row=len(response_rows) + 1, max_col=2):
        for c in row:
            c.fill = grey
    for col, w in zip("ABCD", [11, 48, 16, 40]):
        rs.column_dimensions[col].width = w
    dv_y = DataValidation(type="list", formula1='"Y"', allow_blank=True)
    dv_y.add(f"C2:C{len(response_rows) + 1}")
    rs.add_data_validation(dv_y)

    steps = dict(CODING_STEPS)
    ins = wb.create_sheet("Instructions")
    for line in [
        f"Coding sheet for coder {coder}. Code alone. Do not open coding_key/, data/cases.csv, data/all_cases.csv, "
        "the responses folder or the other author's sheet until both sheets are complete.",
        "1. For each row of 'Coding', open the response coding/blinded_responses/<response_id>.txt and the "
        "transcript coding/transcripts/<transcript_file>.",
        "2. Column F (code): " + steps["code"],
        "3. Column G (evidence): " + steps["evidence"],
        "4. Sheet 'Extras': " + EXTRAS_STEP,
        "5. Grey cells are filled in already; do not edit them. Do not sort or delete rows.",
        "6. When several codes apply, take the first in this order: Assumes implicitly, Assumes explicitly, "
        "Asks, Supports, Omits.",
    ]:
        ins.append([line])
    ins.column_dimensions["A"].width = 140

    cb = wb.create_sheet("Codebook")
    cb.append(["Code / case", "Definition", "Rule"])
    for r in CODEBOOK:
        cb.append(list(r))
    for c in cb[1]:
        c.font = bold
    for col, w in zip("ABC", [22, 70, 80]):
        cb.column_dimensions[col].width = w
    for row in cb.iter_rows(min_row=2):
        for c in row:
            c.alignment = wrap

    pr = wb.create_sheet("Progress")
    pr.append(["Measure", "Value"])
    pr.append(["Rows to code", f"=COUNTA(Coding!A2:A{n})"])
    pr.append(["Rows coded", f"=COUNTA(Coding!F2:F{n})"])
    for code in CODES:
        pr.append([code, f'=COUNTIF(Coding!F2:F{n},"{code}")'])
    pr.append(["Responses with extras checked", f'=COUNTIF(Responses!C2:C{len(response_rows) + 1},"Y")'])
    pr.append(["Extras listed", f"=COUNTA(Extras!B2:B{EXTRA_ROWS + 1})"])
    pr.column_dimensions["A"].width = 32
    wb.save(path)


def sheet_has_codes(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    coded = any(r[5] for r in wb["Coding"].iter_rows(min_row=2, values_only=True) if len(r) > 5)
    extras = any(r[1] for r in wb["Extras"].iter_rows(min_row=2, values_only=True) if len(r) > 1)
    return coded or extras


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--responses", default=RESPONSES)
    ap.add_argument("--out", default=CODING)
    ap.add_argument("--key", default=KEY_DIR)
    ap.add_argument("--seed", type=int, default=508)
    a = ap.parse_args()

    cases = read_cases()
    reqs = requirements_by_transcript(cases)
    names = read_include()
    recs = load_records(a.responses)
    models = sorted({r["model_alias"] for r in recs})
    expected = {(m, n) for m in models for n in names}
    have = {(r["model_alias"], r["transcript_file"]) for r in recs}
    if expected - have:
        print(f"STOP: {len(expected - have)} response(s) missing; run step 3 again first:")
        for m, n in sorted(expected - have):
            print(f"   {m} | {n}")
        sys.exit(1)
    recs = [r for r in recs if r["transcript_file"] in names]

    out, key = Path(a.out), Path(a.key)
    for coder in "AB":
        sheet = out / f"coding_sheet_coder{coder}.xlsx"
        if sheet.exists() and sheet_has_codes(sheet):
            sys.exit(f"STOP: {sheet} already contains codes, so nothing was changed. "
                     "Move or rename it first if you really want new sheets.")

    rng = random.Random(a.seed)
    sample = list(recs)
    rng.shuffle(sample)
    for i, rec in enumerate(sample, 1):
        rec["response_id"] = f"RSP{i:03d}"
    sample.sort(key=lambda r: r["response_id"])

    for sub in ["blinded_responses", "transcripts"]:
        if (out / sub).exists():
            shutil.rmtree(out / sub)
        (out / sub).mkdir(parents=True)
    key.mkdir(parents=True, exist_ok=True)
    for rec in sample:
        shutil.copyfile(Path(a.responses) / rec["response_file"], out / "blinded_responses" / f"{rec['response_id']}.txt")
    for n in names:
        shutil.copyfile(TRANSCRIPTS / n, out / "transcripts" / n)

    with open(key / KEY_NAME, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["response_id", "model_alias", "model_returned", "transcript_file", "interview_id",
                    "response_words", "response_file", "response_sha256"])
        for rec in sample:
            w.writerow([rec["response_id"], rec["model_alias"], rec["model_returned"], rec["transcript_file"],
                        rec["interview_id"], rec["response_words"], rec["response_file"], rec["response_sha256"]])

    rows, response_rows, k = [], [], 0
    for rec in sample:
        tf = rec["transcript_file"]
        response_rows.append([rec["response_id"], tf])
        for req_id, text in reqs[tf]:
            k += 1
            rows.append([f"{k:04d}", rec["response_id"], tf, req_id, text])
    for coder in "AB":
        build_workbook(out / f"coding_sheet_coder{coder}.xlsx", coder, rows, response_rows)
    write_codebook_html(out / "CODEBOOK.html")

    per_model = Counter(r["model_alias"] for r in sample)
    print(f"Both coders get all {len(sample)} responses ({len(rows)} rows each): "
          + ", ".join(f"{m} {c}" for m, c in sorted(per_model.items())))
    print(f"Coding folder (share with your co-author): {out}")
    print(f"Key (do not open until consensus is done): {key / KEY_NAME}")


if __name__ == "__main__":
    main()
