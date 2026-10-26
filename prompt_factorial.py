#!/usr/bin/env python3
"""
prompt_factorial.py -- identifiers x program source x prompt, from the existing prompt-control runs (EXPLORATORY, post hoc).

The prompt control scored conditions 1, 2, 5, 6 with the original one-shot prompt and with no demonstration. With the AST factor at
its original level (cid - 1 = 4*I + 2*A + S, A = 0) these are the eight cells of a 2x2x2 design over
    I  identifiers   (0 original, 1 obfuscated)      conditions: 1 = I0 S0, 2 = I0 S1, 5 = I1 S0, 6 = I1 S1
    S  program source (0 real, 1 generator)
    P  prompt         (0 original one-shot, 1 no demonstration)
The prompt control was run after the confirmation results were known, so this analysis is post hoc and must be reported as such.

For each model it computes the seven signed terms on the same scale as the paper's Table 9 (Equation 4):
    r_T = 2^(|T|-3) * sum_c ( prod_{i in T} x_i(c) ) * ybar_c ,   x_i = -1 / +1 (baseline / perturbed level),
with program-level percentile bootstrap intervals (resampling programs, the same programs in all eight cells; 10,000 resamples,
seed 20261012), two-sided bootstrap p-values and Holm correction within the model's seven terms. Terms are in accuracy points.
It also prints the simple effects that read the three-way term: the generator penalty (S1 - S0) at each identifier x prompt cell.

Input per model: the rerun jsonl of the original prompt and of the no-demonstration prompt, as written by cafa_revision.py rerun
(one JSON object per line with sample_index, condition_id, status, correct). Only programs with status "ok" in all eight cells are used.

Usage (one --model per model; names are free text):
  python3 prompt_factorial.py --out prompt_factorial.json \
      --model DeepSeek-Coder-6.7B rerun_ds_q4.jsonl rerun_ds_none_q4.jsonl \
      --model Qwen2.5-Coder-7B    rerun_q7_q4.jsonl rerun_q7_none_q4.jsonl  ...
"""
import argparse, json, itertools
import numpy as np

CELLS = {  # (I, S, P) -> condition id, file index
    (0, 0): 1, (0, 1): 2, (1, 0): 5, (1, 1): 6}
TERMS = [("I", (0,)), ("S", (1,)), ("P", (2,)), ("I x S", (0, 1)), ("I x P", (0, 2)), ("S x P", (1, 2)), ("I x S x P", (0, 1, 2))]
ORDER = list(itertools.product((0, 1), repeat=3))   # (I, S, P) of the eight cells


def load(path):
    d = {}
    if path.endswith(".json"):   # main-sweep file (responses_*_confirm.json): per_sample_results[sample][condition] = [correct per pass]
        for si, conds in json.load(open(path))["per_sample_results"].items():
            for ci, v in conds.items():
                d[(int(si), int(ci))] = float(np.mean(v))
        return d
    for l in open(path):
        l = l.strip()
        if l:
            r = json.loads(l)
            if r.get("status") == "ok":
                d[(r["sample_index"], r["condition_id"])] = float(r["correct"])
    return d


def matrix(orig, none):
    """programs x 8 cells in ORDER; only programs complete in all eight cells"""
    prog = sorted({s for (s, c) in orig if c in (1, 2, 5, 6)})
    rows, ids = [], []
    for s in prog:
        row = []
        for (i, src, p) in ORDER:
            cid = CELLS[(i, src)]
            v = (orig if p == 0 else none).get((s, cid))
            if v is None: break
            row.append(v)
        else:
            rows.append(row); ids.append(s)
    return np.array(rows), ids


def contrasts(means):
    """means: (..., 8) in ORDER -> (..., 7) signed terms r_T"""
    X = np.array(ORDER) * 2 - 1                      # -1/+1 coding
    out = []
    for _, T in TERMS:
        sign = np.prod(X[:, list(T)], axis=1)
        out.append(2.0 ** (len(T) - 3) * means @ sign)
    return np.stack(out, axis=-1)


def holm(p):
    order = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for k, j in enumerate(order):
        run = max(run, (m - k) * p[j]); adj[j] = min(1.0, run)
    return adj


def analyse(Y, boot, rng):
    n = len(Y)
    est = contrasts(Y.mean(0))
    idx = rng.integers(0, n, size=(boot, n))
    bs = np.empty((boot, 7))
    for b0 in range(0, boot, 500):                    # chunks keep memory small
        ii = idx[b0:b0 + 500]
        bs[b0:b0 + 500] = contrasts(Y[ii].mean(1))
    lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
    p = np.array([max(1.0 / (boot + 1), 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())) for k in range(7)])
    # generator penalty at each (I, P): S1 - S0
    pen = {}
    for i in (0, 1):
        for q in (0, 1):
            a = ORDER.index((i, 1, q)); b = ORDER.index((i, 0, q))
            d = Y[:, a] - Y[:, b]
            bd = d[idx].mean(1)
            pen[f"I{i} P{q}"] = (d.mean(), *np.percentile(bd, [2.5, 97.5]))
    return est, lo, hi, p, holm(p), pen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", nargs=3, action="append", metavar=("NAME", "ORIG_JSONL", "NONE_JSONL"), required=True)
    ap.add_argument("--out", default="prompt_factorial.json")
    ap.add_argument("--boot", type=int, default=10000); ap.add_argument("--seed", type=int, default=20261012)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    report = {}
    for name, fo, fn in a.model:
        Y, ids = matrix(load(fo), load(fn))
        est, lo, hi, p, ph, pen = analyse(Y, a.boot, rng)
        print(f"\n{name}: {len(ids)} programs complete in all eight cells")
        print(f"  cell means (I,S,P): " + "  ".join(f"{k}:{Y[:, j].mean():.3f}" for j, k in enumerate(["".join(map(str, c)) for c in ORDER])))
        print(f"  {'term':<10}{'effect (pts)':>14}   95% interval          p     Holm p")
        rows = []
        for k, (tn, _) in enumerate(TERMS):
            print(f"  {tn:<10}{100*est[k]:>+13.1f}   [{100*lo[k]:+6.1f}, {100*hi[k]:+6.1f}]  {p[k]:7.4f}  {ph[k]:7.4f}")
            rows.append({"term": tn, "effect": est[k], "lo": lo[k], "hi": hi[k], "p": p[k], "p_holm": ph[k]})
        print("  generator penalty (S1 - S0) in points, by identifiers (I) and prompt (P: 0 one-shot, 1 none):")
        for k, (m, l, h) in pen.items(): print(f"    {k}: {100*m:+6.1f}  [{100*l:+6.1f}, {100*h:+6.1f}]")
        report[name] = {"programs": len(ids), "terms": rows, "penalty": {k: list(map(float, v)) for k, v in pen.items()}}
    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\nwritten {a.out}  (post hoc, exploratory; Holm within each model's seven terms)")


if __name__ == "__main__":
    main()
