#!/usr/bin/env python3
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from study import (CASES, DATA, GROUP, INCLUDE, LABEL_MAP, LABELS, N_REQUIREMENTS, SCENARIO,  # noqa: E402
                   SOURCE_LABELS, TRANSCRIPTS, read_include, sha256)

EXPECTED = {"interviews": 11, "Elicited": 72, "Partially elicited": 22, "Not elicited": 38}


def main():
    problems = []
    names = read_include(INCLUDE)
    with open(SOURCE_LABELS, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        text_col = next(c for c in rd.fieldnames if c.startswith("requirement"))
        source = list(rd)

    rows = []
    for r in source:
        if r["transcript_file"] not in names:
            continue
        if r["scenario"] != SCENARIO:
            problems.append(f"{r['transcript_file']} is not a {SCENARIO} interview")
        if r["original_LLMREI_label"] not in LABEL_MAP:
            problems.append(f"unknown label {r['original_LLMREI_label']!r} in {r['transcript_file']} {r['req_id']}")
            continue
        label = LABEL_MAP[r["original_LLMREI_label"]]
        rows.append(dict(interview_id=r["interview_id"], transcript_file=r["transcript_file"],
                         scenario=r["scenario"], req_id=r["req_id"], requirement=r[text_col].strip(),
                         llmrei_label=label, label_group=GROUP[label]))
    rows.sort(key=lambda r: (r["transcript_file"], int(r["req_id"].lstrip("R"))))

    # ---- checks against the paper
    per = defaultdict(Counter)
    for r in rows:
        per[r["transcript_file"]][r["llmrei_label"]] += 1
    missing_labels = [n for n in names if n not in per]
    if missing_labels:
        problems.append(f"no labels in {SOURCE_LABELS.name} for: {missing_labels}")
    for n, c in per.items():
        if sum(c.values()) != N_REQUIREMENTS:
            problems.append(f"{n} has {sum(c.values())} requirements, expected {N_REQUIREMENTS}")
        if c["Elicited"] == 0 or c["Elicited"] == sum(c.values()):
            print(f"NOTE: {n} lacks one of the two groups; it is left out of the paired comparisons.")
    totals = Counter(r["llmrei_label"] for r in rows)
    got = {"interviews": len(per), **{l: totals[l] for l in LABELS}}
    if got != EXPECTED:
        problems.append(f"counts {got} differ from the paper {EXPECTED}")
    texts = defaultdict(set)
    for r in rows:
        texts[r["req_id"]].add(r["requirement"])
    if any(len(v) > 1 for v in texts.values()):
        problems.append("the same req_id has different wording in different interviews")

    manifest = []
    for n in names:
        p = TRANSCRIPTS / n
        if not p.exists():
            problems.append(f"transcript missing: {p}")
            continue
        t = p.read_text(encoding="utf-8")
        if not t.strip():
            problems.append(f"transcript empty: {p}")
        manifest.append(dict(transcript_file=n, words=len(t.split()),
                             stakeholder_turns=sum(1 for l in t.splitlines() if l.startswith("Stakeholder:")),
                             interviewer_turns=sum(1 for l in t.splitlines() if l.startswith("Interviewer:")),
                             sha256=sha256(t)))

    if problems:
        print("STOP, the data does not match the method:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    with open(CASES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(DATA / "transcripts_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0]))
        w.writeheader()
        w.writerows(manifest)

    print(f"{len(per)} interviews, {len(rows)} interview-requirement pairs:")
    print(f"  {'transcript':<48}{'Elicited':>9}{'Partial':>9}{'Not':>6}")
    for n in names:
        c = per[n]
        print(f"  {n:<48}{c['Elicited']:>9}{c['Partially elicited']:>9}{c['Not elicited']:>6}")
    print(f"  {'Total':<48}{totals['Elicited']:>9}{totals['Partially elicited']:>9}{totals['Not elicited']:>6}")
    nfe = totals["Partially elicited"] + totals["Not elicited"]
    print(f"Not fully elicited: {nfe} of {len(rows)} ({nfe / len(rows):.0%}). Matches the paper.")
    print(f"Wrote {CASES.relative_to(DATA.parent)} and data/transcripts_manifest.csv")


if __name__ == "__main__":
    main()
