#!/usr/bin/env python3

import argparse
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheets import completeness, read_coder  # noqa: E402
from study import AGREEMENT, ASSUMES, CODES, CODING, EXTRA_FINAL, ROUND, SHORT, now_utc, sheet_name  # noqa: E402

TARGET = 0.80


def kappa(pairs, labels):
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[l] * cb[l] for l in labels) / (n * n)
    return po, ((po - pe) / (1 - pe) if pe < 1 else 1.0)


def alpha_nominal(units):
    """Krippendorff's alpha (nominal) for a list of units, each a list of the codes given to it."""
    o = defaultdict(float)
    for vals in units:
        vals = [v for v in vals if v not in (None, "")]
        m = len(vals)
        if m < 2:
            continue
        for i, c in enumerate(vals):
            for j, k in enumerate(vals):
                if i != j:
                    o[(c, k)] += 1 / (m - 1)
    n_c = Counter()
    for (c, _), v in o.items():
        n_c[c] += v
    n = sum(n_c.values())
    if n <= 1:
        return float("nan")
    d_o = sum(v for (c, k), v in o.items() if c != k)
    d_e = sum(n_c[c] * n_c[k] for c in n_c for k in n_c if c != k)
    if d_e == 0:
        return 1.0 if d_o == 0 else float("nan")
    return 1 - (n - 1) * d_o / d_e


def landis_koch(k):
    if k != k:
        return "n/a"
    for lim, word in [(0, "poor"), (0.2, "slight"), (0.4, "fair"), (0.6, "moderate"), (0.8, "substantial")]:
        if k <= lim:
            return word
    return "almost perfect"


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def file_hash(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def measures(a, b):
    """Agreement numbers for two complete coders: five codes and the two yes/no splits."""
    keys = sorted(k for k in set(a["codes"]) & set(b["codes"])
                  if a["codes"][k]["code"] in CODES and b["codes"][k]["code"] in CODES)
    pairs = [(a["codes"][k]["code"], b["codes"][k]["code"]) for k in keys]
    res = dict(keys=set(keys), n=len(pairs), disagree=sum(x != y for x, y in pairs),
               extras=(len(a["extras"]), len(b["extras"])))
    for name, f, labels in [("Five codes", lambda x: x, CODES),
                            ("Assumes vs. other", lambda x: x in ASSUMES, [True, False]),
                            ("Asks vs. other", lambda x: x == "Asks", [True, False])]:
        pp = [(f(x), f(y)) for x, y in pairs]
        po, k = kappa(pp, labels)
        res[name] = (po, k, alpha_nominal([list(p) for p in pp]))
    per_a = Counter(e["response_id"] for e in a["extras"])
    per_b = Counter(e["response_id"] for e in b["extras"])
    res["extras_diff"] = sum(per_a[r] != per_b[r] for r in set(per_a) | set(per_b))
    return res


def compare_with_round1(coding, a, b):
    """Lines comparing round 1 (coding_sheet_coderA.xlsx / B.xlsx) with the current round."""
    p1a, p1b = coding / sheet_name("A", 1), coding / sheet_name("B", 1)
    if not (p1a.exists() and p1b.exists()):
        return [f"Round 1 vs round {ROUND}: round-1 sheets not found in {coding} ({p1a.name}, {p1b.name}), "
                "so no comparison."]
    a1, b1 = read_coder(p1a), read_coder(p1b)
    if completeness(a1, "A") + completeness(b1, "B"):
        return [f"Round 1 vs round {ROUND}: the round-1 sheets are not complete, so no comparison."]
    r1, r2 = measures(a1, b1), measures(a, b)
    out = [f"Round 1 vs round {ROUND} (each measured on its own independent codes, before its consensus):",
           f"{'':24}{'Round 1':^26}{'Round ' + str(ROUND):^26}",
           f"{'':24}" + f"{'agree':>8}{'kappa':>9}{'alpha':>9}" * 2]
    for name in ["Five codes", "Assumes vs. other", "Asks vs. other"]:
        out.append(f"{name:24}" + "".join(f"{po:>8.1%}{k:>9.3f}{al:>9.3f}" for po, k, al in (r1[name], r2[name])))
    out.append(f"{'Disagreements':24}{r1['disagree']:>26}{r2['disagree']:>26}")
    out.append(f"{'Extras listed (A / B)':24}{'%d / %d' % r1['extras']:>26}{'%d / %d' % r2['extras']:>26}")
    out.append(f"{'Responses, extras differ':24}{r1['extras_diff']:>26}{r2['extras_diff']:>26}")
    if r1["keys"] != r2["keys"]:
        out.append(f"WARNING: the round-1 and round-{ROUND} sheets do not have the same rows "
                   "(different response IDs or requirements?), so the rounds are not on the same evaluations.")
    return out


def write_consensus(path, a, b, disagreements):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    bold, wrap, grey = Font(bold=True), Alignment(wrap_text=True, vertical="top"), PatternFill("solid", fgColor="E7E6E6")

    ws = wb.active
    ws.title = "Codes"
    ws.append(["response_id", "req_id", "transcript_file", "requirement", "code_A", "evidence_A",
               "code_B", "evidence_B", "consensus_code", "consensus_evidence", "notes"])
    for k in disagreements:
        ra, rb = a["codes"][k], b["codes"][k]
        ws.append([k[0], k[1], ra["transcript_file"], ra["requirement"], ra["code"], ra["evidence"],
                   rb["code"], rb["evidence"]])
    n = len(disagreements) + 1
    for c in ws[1]:
        c.font = bold
    for row in ws.iter_rows(min_row=2, max_row=n, max_col=8):
        for c in row:
            c.fill, c.alignment = grey, wrap
    for col, w in zip("ABCDEFGHIJK", [11, 7, 20, 40, 16, 35, 16, 35, 18, 35, 25]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "I2"
    dv = DataValidation(type="list", formula1='"' + ",".join(CODES) + '"', allow_blank=True)
    dv.add(f"I2:I{max(n, 2)}")
    ws.add_data_validation(dv)

    ex = wb.create_sheet("Extras")
    ex.append(["extra_id", "response_id", "coder", "statement", "class", "transcript evidence",
               "same_as (on A rows: the matching B extra_id)", "final (Supported/Unsupported/Drop)", "notes"])
    rows = []
    for coder, data in [("A", a), ("B", b)]:
        for e in data["extras"]:
            rows.append(dict(e, coder=coder))
    rows.sort(key=lambda e: (e["response_id"], e["coder"], e["sheet_row"]))
    counters = Counter()
    for e in rows:
        counters[e["coder"]] += 1
        e["extra_id"] = f"{e['coder']}{counters[e['coder']]:04d}"
    b_by_resp = defaultdict(list)
    for e in rows:
        if e["coder"] == "B":
            b_by_resp[e["response_id"]].append(e)
    used = set()
    for e in rows:  # suggest matches where both coders wrote the same text
        if e["coder"] != "A":
            continue
        for f in b_by_resp[e["response_id"]]:
            if f["extra_id"] not in used and norm(f["statement"]) and norm(f["statement"]) == norm(e["statement"]):
                e["same_as"], used = f["extra_id"], used | {f["extra_id"]}
                if e["cls"] == f["cls"]:
                    e["final"] = e["cls"]
                e["auto"] = "same_as suggested (identical text); check it"
                break
    for e in rows:
        ex.append([e["extra_id"], e["response_id"], e["coder"], e["statement"], e["cls"],
                   e["transcript_evidence"], e.get("same_as", ""), e.get("final", ""), e.get("auto", "")])
    m = len(rows) + 1
    for c in ex[1]:
        c.font, c.alignment = bold, wrap
    for row in ex.iter_rows(min_row=2, max_row=m, max_col=6):
        for c in row:
            c.fill, c.alignment = grey, wrap
    for col, w in zip("ABCDEFGHI", [9, 11, 6, 55, 12, 35, 18, 18, 30]):
        ex.column_dimensions[col].width = w
    ex.freeze_panes = "G2"
    dv2 = DataValidation(type="list", formula1='"' + ",".join(EXTRA_FINAL) + '"', allow_blank=True)
    dv2.add(f"H2:H{max(m, 2)}")
    ex.add_data_validation(dv2)

    ins = wb.create_sheet("Instructions")
    for line in [
        "Fill this in together, after the agreement report is saved. Do not change the grey cells.",
        "Sheet Codes: for every row, agree on consensus_code (one of the five codes). Add consensus_evidence "
        "if neither coder's evidence fits the agreed code.",
        "Sheet Extras, rows listed per response, A's extras first:",
        "  - Same extra listed by both coders: on coder A's row, write B's extra_id in same_as and set final. "
        "B's row is then counted as a duplicate (leave its final empty).",
        "  - Extra listed by only one coder: set final to Supported, Unsupported, or Drop (not a real extra).",
        "  - Matches suggested by the script (identical text) are pre-filled; check them.",
        "Then press step 5 again.",
    ]:
        ins.append([line])
    ins.column_dimensions["A"].width = 140
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--coding", default=CODING)
    ap.add_argument("--out", default=AGREEMENT)
    ap.add_argument("--partial", action="store_true", help="progress check on rows both coded so far; saves nothing")
    a_ = ap.parse_args()
    coding, out = Path(a_.coding), Path(a_.out)
    pa, pb = coding / sheet_name("A"), coding / sheet_name("B")
    a, b = read_coder(pa), read_coder(pb)

    problems = completeness(a, "A") + completeness(b, "B")
    if set(a["codes"]) != set(b["codes"]):
        problems.append("the two sheets do not have the same rows (were rows deleted or sorted?)")
    if problems and not a_.partial:
        print("STOP: the sheets are not complete yet, so nothing was saved:")
        for p in problems:
            print("  -", p)
        print("Finish the coding, or run with --partial for a progress check.")
        sys.exit(1)

    keys = sorted(k for k in set(a["codes"]) & set(b["codes"]) if a["codes"][k]["code"] and b["codes"][k]["code"]
                  and a["codes"][k]["code"] in CODES and b["codes"][k]["code"] in CODES)
    pairs = [(a["codes"][k]["code"], b["codes"][k]["code"]) for k in keys]
    lines = []
    say = lines.append
    say(f"Intercoder reliability, round {ROUND}, {now_utc()} UTC" + ("  [PARTIAL - progress check only]" if a_.partial else ""))
    say(f"Sheets: {pa.name} (sha256 {file_hash(pa)}), {pb.name} (sha256 {file_hash(pb)})")
    say(f"Evaluations coded by both: {len(pairs)}  (responses: {len({k[0] for k in keys})})")
    po, k = kappa(pairs, CODES)
    al = alpha_nominal([list(p) for p in pairs])
    say(f"Five codes:          agreement {po:.1%}   Cohen's kappa {k:.3f} ({landis_koch(k)})   "
        f"Krippendorff's alpha {al:.3f}")
    coll = [(x in ASSUMES, y in ASSUMES) for x, y in pairs]
    po2, k2 = kappa(coll, [True, False])
    al2 = alpha_nominal([list(p) for p in coll])
    say(f"Assumes vs. other:   agreement {po2:.1%}   Cohen's kappa {k2:.3f} ({landis_koch(k2)})   "
        f"Krippendorff's alpha {al2:.3f}   (supplementary)")
    coll3 = [(x == "Asks", y == "Asks") for x, y in pairs]
    po3, k3 = kappa(coll3, [True, False])
    al3 = alpha_nominal([list(p) for p in coll3])
    say(f"Asks vs. other:      agreement {po3:.1%}   Cohen's kappa {k3:.3f} ({landis_koch(k3)})   "
        f"Krippendorff's alpha {al3:.3f}   (supplementary)")
    say("")
    say("Confusion (rows = coder A, columns = coder B):")
    cm = Counter(pairs)
    say(" " * 20 + "".join(f"{SHORT[c]:>7}" for c in CODES) + f"{'total':>8}")
    for ca in CODES:
        say(f"{ca:>20}" + "".join(f"{cm[(ca, cb)]:>7}" for cb in CODES) + f"{sum(cm[(ca, cb)] for cb in CODES):>8}")
    say(f"{'total':>20}" + "".join(f"{sum(cm[(ca, cb)] for ca in CODES):>7}" for cb in CODES) + f"{len(pairs):>8}")
    say("")
    for name, d in [("A", a), ("B", b)]:
        c = Counter(e["cls"] for e in d["extras"])
        say(f"Extras listed by coder {name}: {len(d['extras'])} (Supported {c['Supported']}, "
            f"Unsupported {c['Unsupported']})")
    per_a = Counter(e["response_id"] for e in a["extras"])
    per_b = Counter(e["response_id"] for e in b["extras"])
    diff = sorted(r for r in set(per_a) | set(per_b) if per_a[r] != per_b[r])
    say(f"Responses where the two coders listed a different number of extras: {len(diff)}")
    say("(Which extras match is settled in consensus.xlsx; the next press of step 5 reports how many were found by both.)")
    say("")
    if ROUND > 1:
        lines.extend(compare_with_round1(coding, a, b))
        say("")
    if al == al:
        if al >= TARGET:
            say(f"DECISION: alpha {al:.3f} >= {TARGET:.2f}. Target reached: resolve the disagreements in "
                f"{out.name}/consensus.xlsx, then press step 5 again.")
        else:
            say(f"DECISION: alpha {al:.3f} < {TARGET:.2f}. Below target: discuss the disagreements in "
                f"{out.name}/consensus.xlsx, sharpen the codebook (runner/study.py), then recode "
                "(see README, 'If alpha is below 0.80').")
    report = "\n".join(lines)
    print(report)
    if a_.partial:
        return

    out.mkdir(parents=True, exist_ok=True)
    stamp = now_utc().replace(":", "").replace("-", "").replace("+0000", "")
    (out / f"report_{stamp}.txt").write_text(report + "\n", encoding="utf-8")
    disagreements = [k for k in keys if a["codes"][k]["code"] != b["codes"][k]["code"]]
    cons = out / "consensus.xlsx"
    if cons.exists():
        cons = out / "consensus_NEW.xlsx"
        print(f"\n{out.name}/consensus.xlsx already exists and was kept. A fresh one was written to {cons.name}; "
              "if you recoded, rename it to consensus.xlsx.")
    write_consensus(cons, a, b, disagreements)
    print(f"\nSaved: {out / f'report_{stamp}.txt'}")
    print(f"Saved: {cons} ({len(disagreements)} disagreements to resolve, "
          f"{len(a['extras']) + len(b['extras'])} extras to match)")


if __name__ == "__main__":
    main()
