import pandas as pd
from scipy.stats import ttest_rel, friedmanchisquare
from statsmodels.stats.multitest import multipletests

lines = []


def say(text):
    print(text)
    lines.append(text)


# 1. Load the data and attach the model and elicitation group to each coded evaluation
codes = pd.read_csv("final/final_codes.csv")
key = pd.read_csv("coding_key/KEY_do_not_open_until_consensus_is_done.csv")
cases = pd.read_csv("data/cases.csv")

df = codes.merge(key[["response_id", "model_alias"]], on="response_id")
df = df.merge(cases[["transcript_file", "req_id", "label_group"]], on=["transcript_file", "req_id"])
df["assumes"] = df["code"].str.startswith("Assumes").astype(int)
df["asks"] = (df["code"] == "Asks").astype(int)

# 2. Rates per interview, per model, per group (the interview is the unit of analysis)
rates = df.groupby(["label_group", "model_alias", "transcript_file"])[["assumes", "asks"]].mean()


def by_model(group, outcome):
    """Table: one row per interview, one column per model."""
    return rates.loc[group, outcome].unstack("model_alias")


def mean_of_models(group, outcome):
    """One value per interview: the mean of the three models."""
    return by_model(group, outcome).mean(axis=1)


def report(name, x, y):
    t, p = ttest_rel(x, y)
    d = x - y
    dz = d.mean() / d.std()
    say(f"{name}: t = {t:.2f}, p = {p:.3f}, dz = {dz:.2f}")
    return p


# RQ1: how often each outcome happens for not fully elicited requirements (descriptive, no test)
for c in ["Asks", "Supports", "Omits"]:
    df[c.lower()] = (df["code"] == c).astype(int)
outcomes = ["asks", "assumes", "supports", "omits"]
rq1 = (df[df["label_group"] == "Not fully elicited"]
       .groupby(["model_alias", "transcript_file"])[outcomes].mean()   # rate per model per interview
       .groupby("transcript_file").mean()                              # mean of the 3 models
       .mean())                                                        # mean over the 11 interviews
say("RQ1 (not fully elicited, mean over interviews)")
for o in outcomes:
    say(f"  {o}: {rq1[o]:.1%}")

# RQ3: explicit vs implicit assumptions (pooled counts, descriptive, no test)
assumptions = df[df["assumes"] == 1]
say("RQ3 (assumption codes, pooled counts)")
for name, part in [("All", assumptions),
                   ("Elicited", assumptions[assumptions["label_group"] == "Elicited"]),
                   ("Not fully elicited", assumptions[assumptions["label_group"] == "Not fully elicited"])]:
    implicit = (part["code"] == "Assumes implicitly").sum()
    say(f"  {name}: {len(part)} assumptions, {implicit} implicit ({implicit / len(part):.1%})")
table = pd.crosstab(df["model_alias"], df["code"])
for m in ["claude", "gemini", "gpt"]:
    exp = table.loc[m].get("Assumes explicitly", 0)
    imp = table.loc[m].get("Assumes implicitly", 0)
    share = f"{imp / (exp + imp):.1%} implicit" if exp + imp else "no assumptions"
    say(f"  {m}: {exp + imp} assumptions, {imp} implicit ({share})")

# 3. RQ2: not fully elicited vs elicited (paired t-tests)
say("RQ2")
for outcome in ["assumes", "asks"]:
    report(f"  {outcome}",
           mean_of_models("Not fully elicited", outcome),
           mean_of_models("Elicited", outcome))

# 4. RQ4: Friedman tests across the three models (not fully elicited requirements)
say("RQ4 Friedman")
n, k = 11, 3
for outcome in ["assumes", "asks"]:
    m = by_model("Not fully elicited", outcome)
    chi2, p = friedmanchisquare(m["claude"], m["gemini"], m["gpt"])
    w = chi2 / (n * (k - 1))
    say(f"  {outcome}: chi2(2) = {chi2:.2f}, p = {p:.3f}, Kendall's W = {w:.2f}")

# 5. RQ4: pairwise paired t-tests for Assumes, with Holm correction
say("RQ4 pairwise (assumes)")
m = by_model("Not fully elicited", "assumes")
pairs = [("claude", "gemini"), ("claude", "gpt"), ("gemini", "gpt")]
raw_p = [report(f"  {a} vs {b}", m[a], m[b]) for a, b in pairs]
holm_p = multipletests(raw_p, method="holm")[1]
for (a, b), p in zip(pairs, holm_p):
    say(f"  {a} vs {b}: Holm-adjusted p = {p:.3f}")

with open("results/tests_output.txt", "w") as f:
    f.write("\n".join(lines) + "\n")
say("Saved in results/tests_output.txt")