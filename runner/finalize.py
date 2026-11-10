#!/usr/bin/env python3
"""Finalize the coding and extras, after the coders have agreed on every disagreement and every extra."""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheets import completeness, read_coder, read_consensus  # noqa: E402
from study import AGREEMENT, ASSUMES, CATEGORIES, CODES, CODING, FINAL, clean, now_utc, sheet_name  # noqa: E402

CAT_HEAD = ["item_id", "type", "response_id", "req_id", "unsupported content (evidence / statement)",
            "added detail (short)", "category", "notes"]


def read_categories(path):
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True)["Categories"]
    rows = ws.iter_rows(values_only=True)
    head = [clean(h) for h in next(rows)]
    return [dict(zip(head, r)) for r in rows if r and r[0]]


def write_categories(path, items):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Categories"
    ws.append(CAT_HEAD)
    for it in items:
        ws.append([it["item_id"], it["type"], it["response_id"], it["req_id"], it["text"]])
    n = len(items) + 1
    grey, wrap = PatternFill("solid", fgColor="E7E6E6"), Alignment(wrap_text=True, vertical="top")
    for c in ws[1]:
        c.font = Font(bold=True)
    for row in ws.iter_rows(min_row=2, max_row=n, max_col=5):
        for c in row:
            c.fill, c.alignment = grey, wrap
    for col, w in zip("ABCDEFGH", [9, 20, 11, 7, 60, 30, 14, 30]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "F2"
    dv = DataValidation(type="list", formula1='"' + ",".join(CATEGORIES) + '"', allow_blank=True)
    dv.add(f"G2:G{max(n, 2)}")
    ws.add_data_validation(dv)
    ins = wb.create_sheet("Instructions")
    for line in [
        "For RQ3: one row per unsupported detail in the final data (both Assumes codes and the Unsupported extras).",
        "added detail: the invented content in a few words (e.g. '24-hour cancellation deadline').",
        "category: Quantity, Actor, Integration, Technology, Policy, or Other (describe it in notes, so new "
        "categories can be formed).",
        "If one row adds two kinds of detail, copy the row (same item_id) and give each copy one category.",
        "Then press step 5 again.",
    ]:
        ins.append([line])
    ins.column_dimensions["A"].width = 130
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--coding", default=CODING)
    ap.add_argument("--agreement", default=AGREEMENT)
    ap.add_argument("--out", default=FINAL)
    a_ = ap.parse_args()
    coding, agr, out = Path(a_.coding), Path(a_.agreement), Path(a_.out)
    a = read_coder(coding / sheet_name("A"))
    b = read_coder(coding / sheet_name("B"))
    problems = completeness(a, "A") + completeness(b, "B")
    if not (agr / "consensus.xlsx").exists():
        problems.append(f"{agr.name}/consensus.xlsx not found: run step 5 first")
    if problems:
        print("STOP:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    cons = read_consensus(agr / "consensus.xlsx")

    # ---------------------------------------------------------------- codes
    finals, missing = [], []
    for key in sorted(a["codes"], key=lambda k: (k[0], int(k[1].lstrip("R")))):
        ra, rb = a["codes"][key], b["codes"][key]
        row = dict(row_id=ra["row_id"], response_id=key[0], transcript_file=ra["transcript_file"], req_id=key[1])
        if ra["code"] == rb["code"]:
            finals.append(dict(row, code=ra["code"], evidence=ra["evidence"] or rb["evidence"], source="agreed"))
            continue
        c = cons["codes"].get(key)
        if c is None or (c["code_A"], c["code_B"]) != (ra["code"], rb["code"]):
            missing.append(f"{key[0]} {key[1]}: the sheets changed after consensus.xlsx was made; run step 5 again")
            continue
        if c["consensus_code"] not in CODES:
            missing.append(f"{key[0]} {key[1]}: consensus_code is empty or not one of the five codes")
            continue
        ev = c["consensus_evidence"] or (ra["evidence"] if c["consensus_code"] == ra["code"] else
                                         rb["evidence"] if c["consensus_code"] == rb["code"] else "")
        finals.append(dict(row, code=c["consensus_code"], evidence=ev, source="consensus"))

    # ---------------------------------------------------------------- extras
    ex = cons["extras"]
    by_id = {e["extra_id"]: e for e in ex}
    n_listed = Counter(e["coder"] for e in ex)
    if n_listed["A"] != len(a["extras"]) or n_listed["B"] != len(b["extras"]):
        missing.append("the Extras sheets changed after consensus.xlsx was made; run step 5 again")
    dup_of = {}
    for e in ex:
        if e.get("bad_final"):
            missing.append(f"extra {e['extra_id']}: final must be Supported, Unsupported or Drop")
        if e["same_as"]:
            f = by_id.get(e["same_as"])
            if e["coder"] != "A" or f is None or f["coder"] != "B" or f["response_id"] != e["response_id"]:
                missing.append(f"extra {e['extra_id']}: same_as must name a B extra of the same response")
            elif e["same_as"] in dup_of:
                missing.append(f"extra {e['same_as']} is matched twice")
            else:
                dup_of[e["same_as"]] = e["extra_id"]
    final_extras = []
    for e in ex:
        if e["extra_id"] in dup_of:
            continue
        if e["final"] not in ("Supported", "Unsupported", "Drop"):
            missing.append(f"extra {e['extra_id']} ({e['response_id']}): final is empty")
            continue
        if e["final"] == "Drop":
            continue
        partner = by_id.get(e["same_as"]) if e["same_as"] else None
        final_extras.append(dict(extra_id=e["extra_id"], response_id=e["response_id"], statement=e["statement"],
                                 cls=e["final"], found_by="both" if partner else e["coder"],
                                 transcript_evidence=e["transcript_evidence"] or (partner or {}).get("transcript_evidence", "")))
    if missing:
        print(f"STOP: {len(missing)} item(s) still open in {agr.name}/consensus.xlsx:")
        for m in missing[:40]:
            print("  -", m)
        if len(missing) > 40:
            print(f"  ... and {len(missing) - 40} more")
        sys.exit(1)

    out.mkdir(parents=True, exist_ok=True)
    with open(out / "final_codes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["row_id", "response_id", "transcript_file", "req_id", "code", "evidence", "source"])
        w.writeheader()
        w.writerows(finals)
    with open(out / "final_extras.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["extra_id", "response_id", "statement", "cls", "found_by", "transcript_evidence"])
        w.writeheader()
        w.writerows(final_extras)

    # extras agreement (identification and classification), from the matches made in consensus.xlsx
    matched = [(by_id[aid], by_id[bid]) for bid, aid in dup_of.items()]
    n_a, n_b, n_m = n_listed["A"], n_listed["B"], len(matched)
    union = n_a + n_b - n_m
    same_cls = sum(x["cls"] == y["cls"] for x, y in matched)
    lines = [f"Extras agreement, {now_utc()} UTC (from the matches in {agr.name}/consensus.xlsx)",
             f"Listed by A: {n_a}; by B: {n_b}; found by both: {n_m}; only A: {n_a - n_m}; only B: {n_b - n_m}",
             f"Found by both / found by either: {n_m}/{union}" + (f" = {n_m / union:.1%}" if union else ""),
             f"Same class (Supported/Unsupported) among those found by both: {same_cls}/{n_m}"
             + (f" = {same_cls / n_m:.1%}" if n_m else "")]
    (agr / "extras_agreement.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------------------------------------------------------------- categories sheet for RQ3
    items, k = [], 0
    for r in finals:
        if r["code"] in ASSUMES:
            k += 1
            items.append(dict(item_id=f"U{k:04d}", type=r["code"], response_id=r["response_id"],
                              req_id=r["req_id"], text=r["evidence"]))
    for e in final_extras:
        if e["cls"] == "Unsupported":
            k += 1
            items.append(dict(item_id=f"U{k:04d}", type="Unsupported extra", response_id=e["response_id"],
                              req_id="", text=e["statement"]))
    cat = out / "categories.xlsx"
    note = ""
    if cat.exists():
        old = read_categories(cat)
        if any(clean(r.get("category")) for r in old):
            old_keys = {(clean(r["type"]), clean(r["response_id"]), clean(r["req_id"]), clean(r.get(CAT_HEAD[4])))
                        for r in old}
            new_keys = {(i["type"], i["response_id"], i["req_id"], i["text"]) for i in items}
            if old_keys == new_keys:
                note = "final/categories.xlsx already filled in and still matches; kept as it is."
            else:
                write_categories(out / "categories_NEW.xlsx", items)
                note = ("final/categories.xlsx is filled in but no longer matches the final codes; kept it, "
                        "and wrote categories_NEW.xlsx. Copy your categories across.")
            cat = None
    if cat is not None:
        write_categories(cat, items)
        note = f"Wrote final/categories.xlsx ({len(items)} unsupported details to categorise)."

    src = Counter(r["source"] for r in finals)
    codes = Counter(r["code"] for r in finals)
    print(f"Final codes: {len(finals)} ({src['agreed']} agreed, {src['consensus']} by consensus) -> final/final_codes.csv")
    print("   " + ", ".join(f"{c} {codes[c]}" for c in CODES))
    cls = Counter(e["cls"] for e in final_extras)
    print(f"Final extras: {len(final_extras)} (Supported {cls['Supported']}, Unsupported {cls['Unsupported']}) "
          "-> final/final_extras.csv")
    print("\n".join(lines[1:]))
    print(note)


if __name__ == "__main__":
    main()
