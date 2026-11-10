"""Reading the coders' workbooks and the consensus workbook (shared by agreement.py and finalize.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from study import CODES, EXTRA_CLASSES, EXTRA_FINAL, clean  # noqa: E402


def _table(ws):
    rows = ws.iter_rows(values_only=True)
    head = [clean(h) for h in next(rows)]
    return [dict(zip(head, r)) for r in rows]


def _col(row, start):
    """Value of the first column whose header starts with `start`."""
    for k, v in row.items():
        if k.startswith(start):
            return clean(v)
    return ""


def read_coder(path):
    """codes: {(response_id, req_id): dict}, extras: [dict], checked: {response_id: bool}, problems: [str]"""
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    problems, codes, extras, checked = [], {}, [], {}
    for r in _table(wb["Coding"]):
        rid = _col(r, "response_id")
        if not rid:
            continue
        code = _col(r, "code")
        if code and code not in CODES:
            problems.append(f"row {_col(r, 'row_id')}: '{code}' is not one of the five codes")
        codes[(rid, _col(r, "req_id"))] = dict(row_id=_col(r, "row_id"), response_id=rid, req_id=_col(r, "req_id"),
                                               transcript_file=_col(r, "transcript_file"),
                                               requirement=_col(r, "requirement"), code=code,
                                               evidence=_col(r, "evidence"), notes=_col(r, "notes"))
    valid_ids = {k[0] for k in codes}
    for i, r in enumerate(_table(wb["Extras"]), start=2):
        statement, rid, cls = _col(r, "extra statement"), _col(r, "response_id"), _col(r, "class")
        if not (statement or rid or cls):
            continue
        if rid not in valid_ids:
            problems.append(f"Extras row {i}: response_id '{rid}' is missing or unknown")
        if not statement:
            problems.append(f"Extras row {i}: the statement is empty")
        if cls not in EXTRA_CLASSES:
            problems.append(f"Extras row {i}: class must be Supported or Unsupported, not '{cls}'")
        extras.append(dict(sheet_row=i, response_id=rid, statement=statement, cls=cls,
                           transcript_evidence=_col(r, "transcript evidence"), notes=_col(r, "notes")))
    for r in _table(wb["Responses"]):
        rid = _col(r, "response_id")
        if rid:
            checked[rid] = _col(r, "extras_checked").upper() == "Y"
    return dict(codes=codes, extras=extras, checked=checked, problems=problems)


def completeness(coder, name):
    """List of problems that block the agreement check (empty list = sheet complete)."""
    out = list(coder["problems"])
    empty = [v["row_id"] for v in coder["codes"].values() if not v["code"]]
    if empty:
        out.append(f"{len(empty)} of {len(coder['codes'])} rows have no code yet (e.g. rows {', '.join(empty[:5])})")
    unchecked = sorted(r for r, ok in coder["checked"].items() if not ok)
    if unchecked:
        out.append(f"extras_checked is not Y for {len(unchecked)} responses (e.g. {', '.join(unchecked[:5])})")
    return [f"coder {name}: {p}" for p in out]


def read_consensus(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    codes = {}
    for r in _table(wb["Codes"]):
        rid = _col(r, "response_id")
        if rid:
            codes[(rid, _col(r, "req_id"))] = dict(code_A=_col(r, "code_A"), code_B=_col(r, "code_B"),
                                                   consensus_code=_col(r, "consensus_code"),
                                                   consensus_evidence=_col(r, "consensus_evidence"))
    extras = []
    for r in _table(wb["Extras"]):
        if _col(r, "extra_id"):
            extras.append(dict(extra_id=_col(r, "extra_id"), response_id=_col(r, "response_id"),
                               coder=_col(r, "coder"), statement=_col(r, "statement"), cls=_col(r, "class"),
                               transcript_evidence=_col(r, "transcript evidence"),
                               same_as=_col(r, "same_as").upper(), final=_col(r, "final").capitalize()))
    for e in extras:
        if e["final"] and e["final"] not in EXTRA_FINAL:
            e["bad_final"] = True
    return dict(codes=codes, extras=extras)
