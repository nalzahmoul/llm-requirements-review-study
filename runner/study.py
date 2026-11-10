
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"

SOURCE_LABELS = DATA / "all_cases.csv"   # all 216 LLMREI labelled pairs (source, not edited)
CASES = DATA / "cases.csv"               # the 132 Ski pairs used in the study (made by prepare_data.py)
TRANSCRIPTS = DATA / "transcripts"
INCLUDE = HERE / "include.txt"
RESPONSES = ROOT / "responses"
CODING = ROOT / "coding"                 # what the two coders get (no model names, no labels)
KEY_DIR = ROOT / "coding_key"            # response ID -> model; do not open until consensus is done
# Coding round that step 5 works on. Round 1 is kept exactly as it was.
#   ROUND = 1: coding/coding_sheet_coderA.xlsx   + coding_sheet_coderB.xlsx   -> agreement/
#   ROUND = 2: coding/coding_sheet_coderA-2.xlsx + coding_sheet_coderB-2.xlsx -> agreement_round2/
ROUND = 2
AGREEMENT = ROOT / ("agreement" if ROUND == 1 else f"agreement_round{ROUND}")
FINAL = ROOT / "final"
RESULTS = ROOT / "results"

SCENARIO = "Ski"
N_REQUIREMENTS = 12

# ---------------------------------------------------------------- labels
# LLMREI's original labels, kept unchanged (only the spelling is tidied).
LABEL_MAP = {"Elicited": "Elicited", "Partially Elicited": "Partially elicited", "No": "Not elicited"}
LABELS = ["Elicited", "Partially elicited", "Not elicited"]
GROUP = {"Elicited": "Elicited", "Partially elicited": "Not fully elicited", "Not elicited": "Not fully elicited"}
GROUPS = ["Elicited", "Not fully elicited"]

# ---------------------------------------------------------------- codes (paper, Table I)
CODES = ["Supports", "Asks", "Assumes explicitly", "Assumes implicitly", "Omits"]
PRIORITY = ["Assumes implicitly", "Assumes explicitly", "Asks", "Supports", "Omits"]
ASSUMES = {"Assumes explicitly", "Assumes implicitly"}
SHORT = {"Supports": "Sup", "Asks": "Ask", "Assumes explicitly": "A-exp", "Assumes implicitly": "A-imp", "Omits": "Omi"}

EXTRA_CLASSES = ["Supported", "Unsupported"]
EXTRA_FINAL = ["Supported", "Unsupported", "Drop"]
CATEGORIES = ["Quantity", "Actor", "Integration", "Technology", "Policy", "Other"]

# (name, definition, rule): shown on the Codebook sheet and in CODEBOOK.html
CODEBOOK = [
    ("Supports",
     "The LLM states the requirement using only information provided or clearly confirmed by the stakeholder.",
     "Information counts as provided if the stakeholder stated it or clearly agreed when the interviewer raised it. "
     "A general 'yes' to the interviewer's closing summary does not confirm details the stakeholder never mentioned. "
     "Rewording is fine as long as no new detail is added."),
    ("Asks",
     "The LLM requests clarification or identifies missing information without supplying it.",
     "A question that offers options (e.g. 'email or upload?') is still Asks. "
     "A statement such as 'the deadline was not specified' also counts."),
    ("Assumes explicitly",
     "The LLM introduces unsupported information but marks it as an assumption or as requiring confirmation.",
     "E.g. under an 'Assumptions' heading, 'we assume ...', '(to be confirmed)'. It supplies content, so it is not Asks."),
    ("Assumes implicitly",
     "The LLM presents unsupported information as an established requirement without indicating uncertainty.",
     "E.g. the stakeholder wants appointment cancellation but gives no deadline, and the response states a "
     "24-hour deadline. Added details count here even when the rest of the requirement is supported."),
    ("Omits",
     "The LLM neither addresses the requirement nor asks for clarification about it.",
     "Leave the evidence empty."),
    ("Several codes apply",
     "Different parts of the response treat the same requirement differently.",
     "Take the first that applies: Assumes implicitly, Assumes explicitly, Asks, Supports, Omits. "
     "This captures unsupported information even when the response also gives supported content or asks."),
    ("Where to look",
     "The whole response counts: the requirement list, notes, assumptions and open questions.",
     "If one requirement is spread over several statements, judge them together."),
    ("Extras",
     "Requirement statements in the response that match none of the 12 predefined requirements.",
     "Check each against the transcript: Supported if its content comes from the transcript, Unsupported if not "
     "(e.g. an invented quantity, actor, integration, technology or policy). List each distinct one once per "
     "response. Leave out duplicates and clarification questions."),
]

CODING_STEPS = [
    ("code", "Choose Supports, Asks, Assumes explicitly, Assumes implicitly or Omits (see the Codebook)."),
    ("evidence", "Copy the words of the response that justify the code (leave empty for Omits). "
                 "For the two Assumes codes, the evidence must show the unsupported detail."),
]
EXTRAS_STEP = ("For every response, list each extra on its own row of the Extras sheet: the response ID, "
               "the statement (copy it or its first words), and Supported or Unsupported. Then write Y in "
               "'extras_checked' on the Responses sheet, also when a response has no extras.")


# ---------------------------------------------------------------- helpers
def sheet_name(coder: str, rnd: int = None) -> str:
    """File name of a coder's sheet in a given round (default: the current ROUND)."""
    rnd = ROUND if rnd is None else rnd
    return f"coding_sheet_coder{coder}.xlsx" if rnd == 1 else f"coding_sheet_coder{coder}-{rnd}.xlsx"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_include(path=INCLUDE):
    return [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def read_cases(path=CASES):
    """The study's interview-requirement pairs, as a list of dicts (made by prepare_data.py)."""
    if not Path(path).exists():
        raise SystemExit(f"{path} not found. Run step 2 (prepare_data.py) first.")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def requirements_by_transcript(cases):
    out = {}
    for c in cases:
        out.setdefault(c["transcript_file"], []).append((c["req_id"], c["requirement"]))
    return out


def load_records(resp_dir=RESPONSES):
    """Latest usable log record per (model, transcript). Cut-off or empty responses are left out."""
    log_path = Path(resp_dir) / "log.jsonl"
    if not log_path.exists():
        raise SystemExit(f"{log_path} not found. Run step 3 (collect responses) first.")
    latest = {}
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            latest[(rec["model_alias"], rec["transcript_file"])] = rec
    bad = [r for r in latest.values() if r.get("status", "ok") != "ok"]
    for r in bad:
        print(f"WARNING: not usable ({r.get('status')}), re-run step 3: {r['model_alias']} | {r['transcript_file']}")
    good = [r for r in latest.values() if r.get("status", "ok") == "ok"]
    return sorted(good, key=lambda r: (r["model_alias"], r["transcript_file"]))


def clean(v):
    return "" if v is None else str(v).strip()
