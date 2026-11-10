# Study replication package

These scripts follow the Methodology of the paper: 11 Ski interviews from LLMREI, three reviewer models, both authors code all 33 responses, then the analysis.

The easiest way is to run the files in `steps/` in order (open one in VS Code, press Run). Run everything from the project folder (the one with `data/`, `runner/` and `steps/`).

## Reproduce the supplied analysis

Run these commands from the project folder containing `runner/`, `data/`, and `final/`:

```bash
python -m pip install -r runner/requirements.txt
python runner/analyze.py
```

The script prints the statistical results and writes `results/tests_output.txt`. The supplied output is overwritten when the analysis is rerun. Alternatively, run `steps/6_analysis_only.py`. No new model requests or manual recoding are needed for this analysis.

The dependency list includes `openai`, `openpyxl`, `scipy`, `pandas`, and `statsmodels`. Versions are not pinned in this package.

## Key

An API key is needed only to make new model requests (steps 1 and 3). Reproducing the analysis from the supplied data does not require a key.

All three models run through **OpenRouter**. Create a local file named `runner/keys.env` and enter your own key:

```
OPENROUTER_API_KEY=YOUR_API_KEY
```

`keys.env` stays on your computer. Do not upload it to Overleaf or GitHub, e-mail it, or paste it in a chat.

## The steps

| Step | What it does | Output |
|---|---|---|
| 0 | install packages (once) | |
| 1 | one tiny request to each model; every line should say OK | |
| 2 | prepare the data: 11 interviews, 132 pairs (72 Elicited, 22 Partially elicited, 38 Not elicited) | `data/cases.csv` |
| 3 | collect the responses: 3 models x 11 transcripts = 33 | `responses/` |
| 4 | blinded coding sheets, all 33 responses for **both** authors (396 rows each) | `coding/`, `coding_key/` |
| 5 | Process the active coding round, consensus, and analysis (see below) | `agreement/` or `agreement_round2/`, `final/`, `results/` |
| 6 | Reproduce the analysis from the final CSV data | `results/tests_output.txt` |

For a new collection or coding exercise, use a separate copy of the project. Step 3 sends only the requests that are missing, failed, came back empty or reached the 32,000-token limit (those are kept as `.TRUNCATED.txt` / `.EMPTY.txt` and repeated). Steps 4 and 5 never overwrite work you have filled in.

## Coding and computing (steps 4-5)

**How many rows?** Exactly 396 code rows per coder (33 responses x 12 predefined requirements): every requirement gets one code per response, whatever the model wrote, and the priority rule settles cases where it appears several times. What is unknown in advance is the number of **extras**: they come on top, one row each on the Extras sheet (room for 1,500). So in total you code at least 396 items.

**Step 5 is one button.** Put both filled sheets in `coding/` as `coding_sheet_coderA.xlsx` and `coding_sheet_coderB.xlsx` and press Run. Each press does the next thing that can be done:

| Press | What happens |
|---|---|
| sheets not finished | shows what is missing and a progress check; saves nothing |
| sheets finished | agreement report (measured once, before discussion) + `agreement/consensus.xlsx`; you settle it together |
| consensus has open items | lists them |
| consensus done | final codes and extras, then the full analysis in `results/tests_output.txt` |

The agreement is measured again only if the codes in the sheets change (opening and saving in Excel does not count). The individual scripts (`agreement.py`, `finalize.py`, `analyze.py`) can still be run on their own.

### Details

1. Step 4 makes `coding/`: one sheet per author, the response texts as `RSP001.txt` ... (random IDs, no model names), copies of the transcripts and `CODEBOOK.html`. The sheets show the 12 predefined requirements but not their LLMREI labels. You use `coding_sheet_coderA.xlsx`; give the folder to Coder B for `coding_sheet_coderB.xlsx`.
2. Each of you codes alone: one of the five codes for every row, the evidence (a quote from the response), and the extras of every response on the Extras sheet (then `extras_checked` = Y). `python runner/agreement.py --partial` shows progress at any time without saving anything.
3. The first full press of step 5 measures percentage agreement, Cohen's kappa and Krippendorff's alpha on all 396 evaluations **before** any disagreement is resolved, and saves the report with a time stamp. Report the first complete one. It also writes `agreement/consensus.xlsx`.
4. In `consensus.xlsx`, settle together every disagreement (`consensus_code`) and every extra (match the ones you both found, and give each a final class: Supported, Unsupported or Drop).
5. The next press merges everything into `final/`, runs the analysis, and reports how many extras you both found and how often you gave them the same class.

### If alpha is below 0.80

Discuss the disagreements in `consensus.xlsx`, sharpen the rules in `runner/study.py` (the codebook lives there), then recode in a second round. Round 1 stays exactly where it is:

| | Round 1 (kept) | Round 2 |
|---|---|---|
| Sheets in `coding/` | `coding_sheet_coderA.xlsx`, `coding_sheet_coderB.xlsx` | `coding_sheet_coderA-2.xlsx`, `coding_sheet_coderB-2.xlsx` |
| Agreement report, consensus | `agreement/` | `agreement_round2/` |

1. Both code again from scratch, alone, on sheets with the same rows and response IDs as round 1, saved with the `-2` names.
2. Put both `-2` sheets in `coding/` next to the round-1 sheets (do not run step 4 again).
3. `ROUND = 2` in `runner/study.py` (it is set). Press step 5: the round-2 report in `agreement_round2/` shows round 1 next to round 2, and `agreement_round2/consensus.xlsx` is the one to settle.
4. Settle `agreement_round2/consensus.xlsx` and press step 5 again: `final/` and `results/` come from round 2.

To look at round 1 again, set `ROUND = 1`; nothing in `agreement/` is overwritten.

## Analysis and research questions

`runner/analyze.py` uses `final/final_codes.csv`, the response mapping in `coding_key/`, and `data/cases.csv`.

- RQ1: outcome rates for not fully elicited requirements, averaged over models and interviews.
- RQ2: differences in assumption and clarification rates between elicited and not fully elicited requirements, using paired t-tests.
- RQ3: explicit versus implicit assumptions, reported as pooled counts and proportions.
- RQ4: model comparisons using Friedman tests and pairwise paired t-tests for assumption rates with Holm correction.

`final/categories.xlsx` is an auxiliary categorization worksheet produced by the coding workflow. It is not an input to the current RQ1-RQ4 analysis.

## Blinding

- Code only from `coding/`. Until the consensus is done, do not open `coding_key/`, `data/cases.csv`, `data/all_cases.csv`, `responses/` or the other author's sheet.
- The analysis is the first place where codes meet model names and labels.

## What is recorded for the paper

`responses/log.jsonl` has one line per request: the model requested and returned, the host that served it, the settings, UTC times and latency, tokens in, out and reasoning, the finish reason and status (ok / truncated / empty), and SHA-256 checksums of the prompt, transcript and response. The random request order is in `responses/plan_seed2027.csv`. `data/transcripts_manifest.csv` has a checksum for every transcript.

## Trying it without a key

```
python runner/run_reviews.py --dry-run
python runner/make_coding_sheets.py --responses responses_dryrun --out coding_dryrun --key coding_key_dryrun
```

The dry run uses a fake model and writes only to `*_dryrun` folders; delete them afterwards.
