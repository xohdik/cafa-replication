#!/usr/bin/env python3
"""
g2_balance.py -- covariate balance and distinguishability of generator programs against the real programs they were matched to.

Compares, on the same samples and with ONE definition of every covariate (g2_features.py):
    real  = condition 1 of the manifest,
    G1    = condition 2 of the manifest (the generator used in the paper),
    G2    = programs from g2_generate.py (g2_base.json), if given.
Reports, for each pair (G1 vs real, G2 vs real, G2 vs G1): the mean in each group, the standardised mean difference (SMD, pooled SD),
the two-sample Kolmogorov-Smirnov statistic, and the share of samples whose program falls within a fixed tolerance of the real
program on the matched properties. It also reports how well a classifier can tell real from generated programs from (a) the numeric
covariates and (b) character n-grams of the normalised code (5-fold, folds grouped by sample so a real program and its twin are never
split), as AUC with a bootstrap interval. AUC near 0.5 means the classifier cannot tell them apart on that representation.
A covariate that is matched by construction is marked 'matched'; the rest are 'free'. SMD |d| < 0.10 is read as balanced.
Usage (cafa env, from capa/):
    python3 g2_balance.py --manifest manifest_confirm.json [--g2 g2_base.json] [--out g2_balance]
Writes g2_balance.json and g2_balance.md. Programs that cannot be run are counted and left out of the covariates that need output.
"""
import argparse
import json
import math
import sys

import numpy as np

from g2_features import code_features, stdin_features, stdout_features, run_code, norm, REAL_LIMITS

MATCHED = {"lines", "cc", "depth", "name_len_mean", "name_single_frac", "out_shape", "in_lines", "in_tokens", "log_in_lines", "log_in_tokens"}
# Gate B of PREREG_G2.md: |SMD| < threshold for each of these (input size on the log scale because real input sizes are heavy-tailed)
GATE_B = {"lines": 0.10, "cc": 0.10, "depth": 0.15, "name_len_mean": 0.10, "name_single_frac": 0.10, "log_in_lines": 0.10, "log_in_tokens": 0.10, "out_shape": 0.10}
HEADLINE = ["lines", "stmts", "cc", "depth", "loops", "ifs", "comps", "has_func", "has_import", "n_input_calls", "uses_stdin_read",
            "n_names", "name_len_mean", "name_single_frac", "name_snake_frac", "n_int_consts", "n_str_consts", "max_int_const", "chars",
            "in_lines", "in_tokens", "log_in_lines", "log_in_tokens", "in_int_frac", "in_mean_digits", "in_has_neg", "in_distinct_tokens_frac",
            "out_lines", "out_shape", "out_tokens", "out_int_frac", "out_first_len", "out_max_abs", "out_first_is_10"]


def row(code, stdin):
    f = code_features(code); f.update(stdin_features(stdin))
    out, err = run_code(code, stdin, **REAL_LIMITS)
    if err is None: f.update(stdout_features(out))
    f["_ok"] = int(err is None)
    return f


def smd(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    sd = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2) if len(a) > 1 and len(b) > 1 else 0.0
    return float((b.mean() - a.mean()) / sd) if sd > 0 else (0.0 if a.mean() == b.mean() else float("inf"))


def ks(a, b):
    a, b = np.sort(np.asarray(a, float)), np.sort(np.asarray(b, float))
    allv = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, allv, side="right") / len(a) - np.searchsorted(b, allv, side="right") / len(b))))


def compare(A, B, names):
    out = {}
    for k in names:
        pairs = [(x[k], y[k]) for x, y in zip(A, B) if k in x and k in y and x.get("_ok", 1) and y.get("_ok", 1)]
        if len(pairs) < 10: continue
        a, b = zip(*pairs)
        out[k] = {"n": len(pairs), "mean_a": float(np.mean(a)), "mean_b": float(np.mean(b)), "smd": smd(a, b), "ks": ks(a, b),
                  "role": "matched" if k in MATCHED else "free"}
    return out


def within_tol(A, B):
    n = ok = 0; res = {"lines": 0, "cc": 0, "depth": 0, "all3": 0, "shape": 0}
    for x, y in zip(A, B):
        if not (x.get("_ok", 1) and y.get("_ok", 1)): continue
        n += 1
        l = abs(x["lines"] - y["lines"]) <= max(1, round(0.1 * x["lines"]))
        c = abs(x["cc"] - y["cc"]) <= max(1, round(0.15 * x["cc"]))
        d = x["depth"] == y["depth"]
        res["lines"] += l; res["cc"] += c; res["depth"] += d; res["all3"] += (l and c and d); res["shape"] += (x.get("out_shape") == y.get("out_shape"))
    return {k: (v / n if n else None) for k, v in res.items()} | {"n": n}


def _auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    order = np.argsort(p, kind="mergesort"); ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    for v in np.unique(p):                                  # average ranks over ties
        m = p == v
        if m.sum() > 1: ranks[m] = ranks[m].mean()
    n1 = y.sum(); n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _lr(Xtr, ytr, Xte, l2=1.0, iters=400, lr=0.5):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    w = np.zeros(A.shape[1]); b = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ w + b, -30, 30)))
        w -= lr * (A.T @ (p - ytr) / len(ytr) + l2 * w / len(ytr)); b -= lr * float((p - ytr).mean())
    return 1 / (1 + np.exp(-np.clip(B @ w + b, -30, 30)))


def _hash_ngrams(code, D=8192):
    import zlib
    v = np.zeros(D, np.float32); b = code.encode()
    for n in (1, 2, 3, 4):
        for i in range(len(b) - n + 1):
            v[zlib.crc32(b[i:i + n]) % D] += 1
    v = np.log1p(v); return v / (np.linalg.norm(v) + 1e-9)


def auc_cv_np(X, y, groups, seed=0, text=False, codes=None):
    """numpy-only fallback when scikit-learn is missing: logistic regression, 5 group folds; text = hashed character 1-4-grams."""
    y, groups = np.asarray(y), np.asarray(groups)
    if text: X = np.stack([_hash_ngrams(c) for c in codes])
    ug = np.unique(groups); rng = np.random.default_rng(seed); rng.shuffle(ug)
    fold = {g: i % 5 for i, g in enumerate(ug)}; f = np.array([fold[g] for g in groups])
    pred = np.zeros(len(y))
    for k in range(5):
        tr, te = f != k, f == k
        pred[te] = _lr(X[tr], y[tr], X[te], l2=(30.0 if text else 1.0))
    auc = _auc(y, pred); lo = []; gi = {g: np.where(groups == g)[0] for g in ug}
    for _ in range(300):
        sel = rng.choice(ug, len(ug)); idx = np.concatenate([gi[g] for g in sel])
        if len(set(y[idx])) == 2: lo.append(_auc(y[idx], pred[idx]))
    return {"auc": auc, "ci95": [float(np.percentile(lo, 2.5)), float(np.percentile(lo, 97.5))], "method": "numpy logistic regression"}


def auc_cv(X, y, groups, seed=0, text=False, codes=None):
    try:
        import sklearn  # noqa: F401
    except ImportError:
        return auc_cv_np(X, y, groups, seed, text, codes)
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    y, groups = np.asarray(y), np.asarray(groups)
    pred = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(np.zeros(len(y)), y, groups):
        if text:
            vec = TfidfVectorizer(analyzer="char", ngram_range=(1, 4), min_df=3, sublinear_tf=True, max_features=60000)
            Xtr = vec.fit_transform([codes[i] for i in tr]); Xte = vec.transform([codes[i] for i in te])
            clf = LogisticRegression(max_iter=2000, C=1.0)
        else:
            Xtr, Xte = X[tr], X[te]; clf = HistGradientBoostingClassifier(max_depth=3, max_iter=150, random_state=seed)
        clf.fit(Xtr, y[tr]); pred[te] = clf.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(y, pred)
    rng = np.random.default_rng(seed); ug = np.unique(groups); lo = []
    gi = {g: np.where(groups == g)[0] for g in ug}
    for _ in range(300):
        sel = rng.choice(ug, len(ug)); idx = np.concatenate([gi[g] for g in sel])
        if len(set(y[idx])) == 2: lo.append(roc_auc_score(y[idx], pred[idx]))
    return {"auc": float(auc), "ci95": [float(np.percentile(lo, 2.5)), float(np.percentile(lo, 97.5))], "method": "scikit-learn"}


def distinguish(R, S, codes_r, codes_s, idx):
    cols = [k for k in HEADLINE if k in R[0] and k in S[0]]
    X = np.array([[r.get(k, 0) for k in cols] for r in R] + [[s.get(k, 0) for k in cols] for s in S], float)
    y = [0] * len(R) + [1] * len(S); g = list(idx) + list(idx)
    out = {"covariates": auc_cv(X, y, g)}
    # without the matched covariates: what is left to tell them apart
    free = [i for i, k in enumerate(cols) if k not in MATCHED]
    out["free_covariates_only"] = auc_cv(X[:, free], y, g)
    out["char_ngrams"] = auc_cv(None, y, g, text=True, codes=codes_r + codes_s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest_confirm.json"); ap.add_argument("--g2", default=None)
    ap.add_argument("--out", default="g2_balance"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-classifier", action="store_true")
    a = ap.parse_args()
    man = json.load(open(a.manifest))["samples"]
    if a.limit: man = man[:a.limit]
    g2 = {r["sample_index"]: r for r in json.load(open(a.g2))["samples"]} if a.g2 else {}
    R, S1, S2, idx = [], [], [], []
    code_r, code_1, code_2 = [], [], []
    for s in man:
        c = {b["condition_id"]: b for b in s["conditions"]}
        if c[1].get("status") != "ok" or c[2].get("status") != "ok" or not c[1].get("source_code") or not c[2].get("source_code"): continue
        i0 = s["sample_index"]
        if a.g2 and (i0 not in g2 or g2[i0].get("status") != "ok"): continue
        in_r = (c[1].get("stdin_cases") or s["stdin_cases"])[0]; in_1 = (c[2].get("stdin_cases") or s["stdin_cases"])[0]
        R.append(row(c[1]["source_code"], in_r)); S1.append(row(c[2]["source_code"], in_1)); code_r.append(norm(c[1]["source_code"])); code_1.append(norm(c[2]["source_code"]))
        if a.g2:
            S2.append(row(g2[i0]["source_code"], g2[i0]["stdin_cases"][0])); code_2.append(norm(g2[i0]["source_code"]))
        idx.append(i0)
    rep = {"n_samples": len(idx), "manifest": a.manifest, "g2": a.g2}
    if a.g2:                                           # selection check: do the samples G2 could not match differ in their real program?
        got, miss = [], []
        for s in man:
            c1 = next((b for b in s["conditions"] if b["condition_id"] == 1), None)
            if not c1 or not c1.get("source_code"): continue
            f = code_features(c1["source_code"]); f.update(stdin_features((c1.get("stdin_cases") or s["stdin_cases"])[0]))
            (got if g2.get(s["sample_index"], {}).get("status") == "ok" else miss).append(f)
        rep["selection_check"] = {"n_matched": len(got), "n_not_matched": len(miss),
                                  "real_program_covariates": {k: {"matched_mean": float(np.mean([x[k] for x in got])), "not_matched_mean": float(np.mean([x[k] for x in miss])) if miss else None,
                                                                   "smd": smd([x[k] for x in got], [x[k] for x in miss]) if len(miss) > 1 else None}
                                                              for k in ("lines", "cc", "depth", "name_len_mean", "name_single_frac", "log_in_tokens", "loops", "ifs")}}
    rep["G1_vs_real"] = {"balance": compare(R, S1, HEADLINE), "within_tolerance": within_tol(R, S1)}
    if a.g2:
        rep["G2_vs_real"] = {"balance": compare(R, S2, HEADLINE), "within_tolerance": within_tol(R, S2)}
        rep["G2_vs_G1"] = {"balance": compare(S1, S2, HEADLINE)}
        rep["share_g2_equal_to_g1_program"] = float(np.mean([x == y for x, y in zip(code_1, code_2)]))
        gb = rep["G2_vs_real"]["balance"]
        rep["gate_B"] = {k: {"smd": gb[k]["smd"], "threshold": t, "pass": abs(gb[k]["smd"]) < t} for k, t in GATE_B.items() if k in gb}
        rep["gate_B_pass"] = all(v["pass"] for v in rep["gate_B"].values())
    if not a.no_classifier:
        try:
            rep["distinguishability"] = {"G1_vs_real": distinguish(R, S1, code_r, code_1, idx)}
            if a.g2: rep["distinguishability"]["G2_vs_real"] = distinguish(R, S2, code_r, code_2, idx)
        except ImportError as e:
            rep["distinguishability"] = {"skipped": str(e)}
    json.dump(rep, open(a.out + ".json", "w"), indent=1)
    # markdown table
    L = ["# Covariate balance: generator programs against the real programs they were matched to", "",
         f"{len(idx)} samples with an executable program in every group. SMD = (generated - real) / pooled SD; |SMD| < 0.10 read as balanced. 'matched' rows were targeted by G2; G1's matching is described in the paper (lines, cyclomatic complexity, nesting depth, output shape).", "",
         "| Covariate | role | real mean | G1 mean | G1 SMD | G1 KS |" + (" G2 mean | G2 SMD | G2 KS | G2 vs G1 SMD |" if a.g2 else ""),
         "|---|---|---|---|---|---|" + ("---|---|---|---|" if a.g2 else "")]
    for k in HEADLINE:
        b1 = rep["G1_vs_real"]["balance"].get(k)
        if not b1: continue
        line = f"| {k} | {b1['role']} | {b1['mean_a']:.2f} | {b1['mean_b']:.2f} | {b1['smd']:+.2f} | {b1['ks']:.2f} |"
        if a.g2:
            b2 = rep["G2_vs_real"]["balance"].get(k); b12 = rep["G2_vs_G1"]["balance"].get(k)
            line += f" {b2['mean_b']:.2f} | {b2['smd']:+.2f} | {b2['ks']:.2f} | {b12['smd']:+.2f} |" if b2 and b12 else " | | | |"
        L.append(line)
    L += ["", "Within tolerance of the real program (lines +-10%, cyclomatic complexity +-15%, depth exact, output shape equal):", "",
          "| Generator | lines | cc | depth | all three | output shape |", "|---|---|---|---|---|---|"]
    for name in ("G1_vs_real", "G2_vs_real"):
        if name in rep:
            w = rep[name]["within_tolerance"]; L.append(f"| {name.split('_')[0]} | {w['lines']:.3f} | {w['cc']:.3f} | {w['depth']:.3f} | {w['all3']:.3f} | {w['shape']:.3f} |")
    if "distinguishability" in rep and "skipped" not in rep["distinguishability"]:
        L += ["", "Classifier AUC for real versus generated (5-fold, grouped by sample; 95% bootstrap interval over samples). 0.5 = indistinguishable.", "",
              "| Comparison | numeric covariates | covariates not matched | character n-grams |", "|---|---|---|---|"]
        for name, d in rep["distinguishability"].items():
            f = lambda x: f"{x['auc']:.3f} [{x['ci95'][0]:.3f}, {x['ci95'][1]:.3f}]"
            L.append(f"| {name} | {f(d['covariates'])} | {f(d['free_covariates_only'])} | {f(d['char_ngrams'])} |")
    if a.g2:
        L += ["", "Gate B (|SMD| of G2 against real, matched covariates; PREREG_G2.md):", "", "| Covariate | G2 SMD | threshold | pass |", "|---|---|---|---|"]
        for k, v in rep["gate_B"].items(): L.append(f"| {k} | {v['smd']:+.3f} | {v['threshold']:.2f} | {'yes' if v['pass'] else 'NO'} |")
        L.append(f"| all | | | {'PASS' if rep['gate_B_pass'] else 'FAIL'} |")
        sc = rep["selection_check"]
        L += ["", f"Selection check: {sc['n_matched']} samples matched, {sc['n_not_matched']} not matched. Mean of the REAL program's covariates in each group:", "",
              "| Covariate | matched | not matched | SMD |", "|---|---|---|---|"]
        for k, v in sc["real_program_covariates"].items():
            L.append(f"| {k} | {v['matched_mean']:.2f} | {(v['not_matched_mean'] if v['not_matched_mean'] is not None else float('nan')):.2f} | {(v['smd'] if v['smd'] is not None else float('nan')):+.2f} |")
    open(a.out + ".md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
