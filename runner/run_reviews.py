#!/usr/bin/env python3
"""
Collect the reviewer responses for "Ask or Assume?" (MO2RE 2027).

Each of the three models reviews each of the 11 Ski transcripts once: 33 responses.
For every (model, transcript) job the script sends ONE stateless request through
OpenRouter, containing the prompt and the complete transcript (no system prompt,
no history, provider default settings), and saves:

  responses/<model_alias>/<transcript_stem>.txt   the response, verbatim
  responses/log.jsonl                             one line per request (see below)
  responses/plan_seed2027.csv                     the random order of the requests

Each log line records the model requested and returned, the host that served it
(serving provider), UTC start/end times, latency, input/output/reasoning tokens,
the finish reason and status (ok / truncated / empty), and SHA-256 checksums of
the prompt, the transcript and the response.

A response that reached the 32,000-token limit, or came back empty, is kept for the
record under a separate name (.TRUNCATED.txt / .EMPTY.txt) and counts as not done:
run the same command again and only those requests are repeated. Finished requests
are never sent twice.

Usage (from the project folder):
  python runner/run_reviews.py --check      # one tiny test call per model
  python runner/run_reviews.py --dry-run    # whole run with a fake model, no key, into responses_dryrun/
  python runner/run_reviews.py              # the study: 33 responses into responses/
"""
import argparse
import csv
import json
import os
import random
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from study import HERE, INCLUDE, RESPONSES, TRANSCRIPTS, now_utc, read_include, sha256  # noqa: E402


def load_keys_file():
    """Read API keys from runner/keys.env (KEY=value per line) if the file exists."""
    f = HERE / "keys.env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and "paste" not in v.lower() and not os.environ.get(k):
            os.environ[k] = v


load_keys_file()


def _reasoning_tokens(u):
    """Hidden reasoning tokens, if the API reports them (they are part of output_tokens)."""
    d = getattr(u, "completion_tokens_details", None)
    if d is None:
        d = (getattr(u, "model_extra", None) or {}).get("completion_tokens_details")
    if isinstance(d, dict):
        return d.get("reasoning_tokens")
    return getattr(d, "reasoning_tokens", None)


def call_openrouter(cfg, prompt):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get(cfg["api_key_env"], "none"),
                    base_url=cfg.get("base_url") or None, timeout=900, max_retries=0)
    kwargs = dict(model=cfg["model"], messages=[{"role": "user", "content": prompt}])
    extra = dict(cfg.get("extra_body") or {})
    if cfg.get("max_tokens"):
        extra["max_tokens"] = cfg["max_tokens"]  # OpenRouter's output limit (includes reasoning tokens)
    if extra:
        kwargs["extra_body"] = extra
    r = client.chat.completions.create(**kwargs)
    ch, u = r.choices[0], r.usage
    return dict(text=ch.message.content or "", model_returned=r.model,
                served_by=(getattr(r, "model_extra", None) or {}).get("provider"),
                input_tokens=getattr(u, "prompt_tokens", None),
                output_tokens=getattr(u, "completion_tokens", None),
                reasoning_tokens=_reasoning_tokens(u),
                finish_reason=ch.finish_reason, truncated=(ch.finish_reason == "length"))


def call_mock(cfg, prompt):
    """Fake model for --dry-run: a short requirements list, sometimes with an assumption or a question."""
    time.sleep(0.01)
    rng = random.Random(sha256(cfg["alias"] + prompt))
    lines = ["# Software Requirements", "", "## Functional requirements",
             "FR-1: The system shall let customers book ski classes and rent equipment online.",
             "FR-2: The system shall keep a central record of reservations, hires and inventory for all three resorts."]
    if rng.random() < 0.6:
        lines.append("FR-3: Customers can cancel a booking up to 24 hours before the start.")
    if rng.random() < 0.5:
        lines.append("FR-4: The system shall integrate with Stripe for card payments.")
    lines += ["", "## Open questions"]
    if rng.random() < 0.5:
        lines.append("Q1: Which weather data provider should the forecasts come from?")
    lines += ["", "## Assumptions", "A1: Reports are generated monthly (to be confirmed)."]
    text = "[DRY RUN - not a real model]\n" + "\n".join(lines) + "\n"
    return dict(text=text, model_returned=cfg["model"] + "-mock", served_by="mock",
                input_tokens=len(prompt) // 4, output_tokens=len(text) // 4, reasoning_tokens=0,
                finish_reason="stop", truncated=False)


VERBOSE = False  # --show-names: print model and transcript names (breaks blinding; only for fixing problems)


def call_with_retry(cfg, prompt, attempts=3):
    fn = call_mock if cfg.get("provider") == "mock" else call_openrouter
    for i in range(attempts):
        try:
            return fn(cfg, prompt)
        except Exception as e:  # rate limits, timeouts, 5xx
            if i == attempts - 1:
                raise
            wait = min(60, 2 ** (i + 1))
            print(f"    error ({type(e).__name__}) -> retry in {wait}s" + (f": {e}" if VERBOSE else ""), flush=True)
            time.sleep(wait)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=HERE / "models.json")
    ap.add_argument("--prompt", default=HERE / "prompt.txt")
    ap.add_argument("--transcripts", default=TRANSCRIPTS)
    ap.add_argument("--include", default=INCLUDE, help="file listing the transcripts to use (one per line)")
    ap.add_argument("--out", default=RESPONSES)
    ap.add_argument("--models", nargs="*", help="model aliases to run (default: all enabled in models.json)")
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds to wait between requests")
    ap.add_argument("--dry-run", action="store_true", help="use a fake model; no key needed; writes responses_dryrun/")
    ap.add_argument("--check", action="store_true", help="one tiny test request per model")
    ap.add_argument("--show-names", action="store_true",
                    help="print model and transcript names while running (breaks the coders' blinding)")
    a = ap.parse_args()
    global VERBOSE
    VERBOSE = a.show_names

    models = [m for m in json.loads(Path(a.config).read_text(encoding="utf-8"))["models"] if m.get("enabled", True)]
    if a.models:
        models = [m for m in models if m["alias"] in a.models]
    if not models:
        sys.exit("No models selected. Check --models and 'enabled' in models.json.")
    if a.dry_run:
        models = [dict(m, provider="mock") for m in models]
        a.out = Path(a.out).with_name(Path(a.out).name + "_dryrun")
    else:
        for m in models:
            if not os.environ.get(m["api_key_env"]):
                sys.exit(f"No API key for '{m['alias']}': paste it into runner/keys.env on the line {m['api_key_env']}=...")

    if a.check:
        print("Setup check: one tiny request per model (a fraction of a cent).")
        ok = True
        for m in models:
            try:
                res = call_with_retry(m, "Reply with the single word OK.", attempts=2)
                print(f"  OK    {m['alias']:7s} requested {m['model']}  ->  returned {res['model_returned']}"
                      + (f" (served by {res.get('served_by')})" if res.get("served_by") else "")
                      + f"  | reply: {res['text'].strip()[:20]!r}")
            except Exception as e:
                ok = False
                print(f"  FAIL  {m['alias']:7s} {m['model']}: {type(e).__name__}: {str(e)[:200]}")
        sys.exit(0 if ok else 1)

    task = Path(a.prompt).read_text(encoding="utf-8").rstrip()
    if "<transcript text>" not in task:
        sys.exit("prompt.txt must contain the placeholder <transcript text>.")
    names = read_include(a.include)
    tdir = Path(a.transcripts)
    missing = [n for n in names if not (tdir / n).exists()]
    if missing:
        sys.exit(f"Transcripts not found in {tdir}: {missing}")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(m["alias"], n) for m in models for n in names]
    random.Random(a.seed).shuffle(jobs)
    with open(out / f"plan_seed{a.seed}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["order", "model_alias", "transcript_file"])
        for i, j in enumerate(jobs, 1):
            w.writerow([i, *j])

    by_alias = {m["alias"]: m for m in models}
    done = skipped = failed = 0
    for i, (alias, name) in enumerate(jobs, 1):
        cfg = by_alias[alias]
        resp_file = out / alias / f"{Path(name).stem}.txt"
        if resp_file.exists():
            skipped += 1
            continue
        transcript = (tdir / name).read_text(encoding="utf-8")
        prompt = task.replace("<transcript text>", transcript)
        # Blinded progress: no model or transcript names, so the person running this can still code.
        print(f"[{i}/{len(jobs)}] request sent" + (f" ({alias} | {name})" if VERBOSE else ""), flush=True)
        t0, start = time.time(), now_utc()
        stop = threading.Event()

        def heartbeat():  # shows the request is still alive while the model thinks and writes
            while not stop.wait(20):
                print(f"    still working... {int(time.time() - t0)} s (normal: the model is thinking/writing)", flush=True)

        threading.Thread(target=heartbeat, daemon=True).start()
        try:
            res = call_with_retry(cfg, prompt)
        except Exception as e:
            stop.set()
            failed += 1
            with open(out / "errors.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(dict(time=now_utc(), model_alias=alias, transcript_file=name,
                                        error=f"{type(e).__name__}: {e}")) + "\n")
            print("    FAILED (details in responses/errors.jsonl; it is repeated when you run this again)"
                  + (f": {e}" if VERBOSE else ""), flush=True)
            continue
        stop.set()
        status = "truncated" if res["truncated"] else ("empty" if not res["text"].strip() else "ok")
        save_to = resp_file if status == "ok" else resp_file.with_name(f"{resp_file.stem}.{status.upper()}.txt")
        save_to.parent.mkdir(parents=True, exist_ok=True)
        save_to.write_text(res["text"], encoding="utf-8")
        stem = Path(name).stem
        rec = dict(order=i, model_alias=alias, model_requested=cfg["model"], model_returned=res["model_returned"],
                   served_by=res.get("served_by"),
                   settings=dict(max_tokens=cfg.get("max_tokens"), sampling="provider default", system_prompt=None),
                   transcript_file=name, scenario=stem.split("_")[0], interview_id=stem.split("_", 1)[1],
                   seed=a.seed, utc_start=start, utc_end=now_utc(), latency_s=round(time.time() - t0, 2),
                   input_tokens=res["input_tokens"], output_tokens=res["output_tokens"],
                   reasoning_tokens=res.get("reasoning_tokens"), finish_reason=res["finish_reason"],
                   status=status, response_words=len(res["text"].split()),
                   prompt_sha256=sha256(task), transcript_sha256=sha256(transcript),
                   response_sha256=sha256(res["text"]), response_file=save_to.relative_to(out).as_posix())
        with open(out / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        time.sleep(a.delay)
        if status != "ok":
            failed += 1
            print(f"    WARNING: response {status}. It is set aside and repeated when you run this again.", flush=True)
            continue
        print(f"    done in {int(time.time() - t0)} s", flush=True)
        done += 1

    total_ok = sum(1 for al, n in jobs if (out / al / f"{Path(n).stem}.txt").exists())
    print(f"\nThis run: {done} new, {skipped} already saved, {failed} to repeat. "
          f"Usable responses: {total_ok} of {len(jobs)}. Output: {out}")
    if failed:
        print("Run the same command again to repeat the failed or cut-off requests (see errors.jsonl / log.jsonl).")


if __name__ == "__main__":
    main()