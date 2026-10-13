#!/usr/bin/env python3
"""
cafa_revision.py -- one file, four subcommands, for the data-dependent revision items.
Run it from the repository root (next to scoring_harness.py).

  checks    CPU only.  Complete-case audit, re-derive the 7 terms + 4 simple effects,
            I x S inside output-length strata, I x S by problem popularity
            (CodeNet submission count), and the 456/457 problem-count audit.
  rerun     GPU.       Re-score chosen conditions with the SAME harness settings and
            SAVE the prediction text (the original run kept only 0/1 scores).
  classify  CPU.       Wrong-answer taxonomy for two conditions from a rerun file.
  q8        CPU.       Q4_K_M original scores vs Q8_0 rerun on conditions 1,2,5,6.

Condition ids: cid-1 = 4*I + 2*A + S   (C1 = 0,0,0 ... C8 = 1,1,1).
Nothing here edits an existing file; outputs are new files.
"""
import argparse, csv, glob, json, math, os, re, sys, time, collections

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "perturbations"))

# ----------------------------------------------------------------- design algebra
TERMS = ["I", "A", "S", "IA", "IS", "AS", "IAS"]
BIT = {"S": 0, "A": 1, "I": 2}


def level(cid, f):
    return ((cid - 1) >> BIT[f]) & 1


def sgn(cid, f):
    return 1 if level(cid, f) else -1


def term_weights(term):
    w = np.array([np.prod([sgn(c, f) for f in term]) for c in range(1, 9)], float)
    return w / 2 ** (3 - len(term))          # I x S == [m(6,8)-m(2,4)] - [m(5,7)-m(1,3)]


W7 = np.stack([term_weights(t) for t in TERMS], 1)          # 8 x 7


def simple_weights():
    """I|S=0, I|S=1, S|I=0, S|I=1 (A averaged), as in Table 7."""
    out = {}
    for name, (fx, fy, lv) in {"I|real": ("I", "S", 0), "I|synth": ("I", "S", 1),
                               "S|orig-names": ("S", "I", 0), "S|obf-names": ("S", "I", 1)}.items():
        w = np.zeros(8)
        for c in range(1, 9):
            if level(c, fy) == lv:
                w[c - 1] = (1 if level(c, fx) else -1) / 2.0
        out[name] = w
    return out


def boot(E, B=10000, seed=0, chunk=250):
    """E: n x k per-program contrast values -> B x k bootstrap means (program-level)."""
    n, k = E.shape
    rng = np.random.default_rng(seed)
    out = np.empty((B, k))
    for s in range(0, B, chunk):
        m = min(chunk, B - s)
        out[s:s + m] = E[rng.integers(0, n, (m, n))].mean(1)
    return out


def pval(b):
    B = len(b)
    return min(1.0, 2 * min((np.sum(b <= 0) + 1) / (B + 1), (np.sum(b >= 0) + 1) / (B + 1)))


def holm(ps):
    order = np.argsort(ps)
    adj = np.empty(len(ps))
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, (len(ps) - r) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def ci(b):
    lo, hi = np.percentile(b, [2.5, 97.5])
    return lo, hi


def fmt(x):
    return f"{x:+.3f}"


def spearman(x, y):
    try:
        from scipy.stats import spearmanr
        r = spearmanr(x, y)
        return float(r.statistic if hasattr(r, "statistic") else r[0]), float(r.pvalue if hasattr(r, "pvalue") else r[1])
    except Exception:
        def rk(a):
            a = np.asarray(a, float)
            u, inv = np.unique(a, return_inverse=True)
            cs = np.cumsum(np.bincount(inv))
            avg = cs - (np.bincount(inv) - 1) / 2.0
            return avg[inv]
        return float(np.corrcoef(rk(x), rk(y))[0, 1]), float("nan")


# ----------------------------------------------------------------- data loading
def load_orig(path):
    """responses_*.json -> {(sample_index, cid): score in [0,1]} (cells with no score are absent)."""
    d = json.load(open(path))
    out = {}
    for si, cs in d["per_sample_results"].items():
        for cid, v in cs.items():
            vals = [x for x in (v if isinstance(v, list) else [v]) if x is not None]
            if vals:
                out[(int(si), int(cid))] = float(np.mean(vals))
    return out


def load_jsonl(path):
    recs = []
    if not os.path.exists(path):
        return recs
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass          # a half-written last line after a kill
    return recs


def rerun_scores(path):
    out = {}
    for r in load_jsonl(path):
        if r.get("status") == "ok":
            out[(r["sample_index"], r["condition_id"])] = 1.0 if r["correct"] else 0.0
    return out


def matrix(scores, cids=range(1, 9)):
    by = collections.defaultdict(dict)
    for (s, c), v in scores.items():
        by[s][c] = v
    cids = list(cids)
    keep = sorted(s for s, d in by.items() if all(c in d for c in cids))
    return keep, np.array([[by[s][c] for c in cids] for s in keep], float)


def stdin_of(s, built):
    cases = built.get("stdin_cases") or s.get("stdin_cases")
    return cases[0] if cases else None


# ----------------------------------------------------------------- checks
def cmd_checks(a):
    man = json.load(open(a.manifest))
    samples = man["samples"]
    pid_of = {s["sample_index"]: s.get("problem_id") for s in samples}
    print(f"== manifest {a.manifest}: {len(samples)} samples, {len(set(pid_of.values()))} distinct problems")

    # 1. problem-count audit (456 vs 457)
    print("\n== problem-id audit (distinct problem ids per file; overlap with the confirmation set)")
    conf = set(pid_of.values())
    for pat in ["manifest*.json", "pairs_confirm.json", "rq4*.jsonl"]:
        for f in sorted(glob.glob(os.path.join(HERE, pat))):
            try:
                if f.endswith(".jsonl"):
                    ids = {r.get("problem_id") for r in load_jsonl(f)}
                else:
                    d = json.load(open(f))
                    rows = d["samples"] if isinstance(d, dict) and "samples" in d else d
                    ids = {r.get("problem_id") for r in rows if isinstance(r, dict)}
                ids.discard(None)
                print(f"  {os.path.basename(f):38s} n_problems={len(ids):5d}  overlap_with_confirm={len(ids & conf)}")
            except Exception as e:
                print(f"  {os.path.basename(f):38s} (not read: {type(e).__name__})")

    # 2. complete cases + 7 terms
    sc = load_orig(a.responses)
    keep, Y = matrix(sc)
    dropped = sorted(set(pid_of) - set(keep))
    print(f"\n== {a.responses}: complete cases = {len(keep)} of {len(samples)}; dropped indices: {dropped[:12]}{' ...' if len(dropped) > 12 else ''}")
    print("   condition means C1..C8: " + " ".join(f"{m:.3f}" for m in Y.mean(0)))
    E = Y @ W7
    B = boot(E, a.boot)
    est = E.mean(0)
    ps = np.array([pval(B[:, j]) for j in range(7)])
    adj = holm(ps)
    print("\n== seven terms (signed; program-level bootstrap, Holm over 7)")
    for j, t in enumerate(TERMS):
        lo, hi = ci(B[:, j])
        print(f"   {t:4s} {fmt(est[j])} [{fmt(lo)},{fmt(hi)}]  p={ps[j]:.4f}  holm={adj[j]:.4f}")
    sw = simple_weights()
    Es = np.stack([Y @ w for w in sw.values()], 1)
    Bs = boot(Es, a.boot)
    print("\n== four simple effects (Table 7 definition, A averaged)")
    for j, k in enumerate(sw):
        lo, hi = ci(Bs[:, j])
        print(f"   {k:14s} {fmt(Es[:, j].mean())} [{fmt(lo)},{fmt(hi)}]")

    # 3. I x S by output-length stratum
    iS = TERMS.index("IS")
    if not a.skip_strata:
        from scoring_harness import ground_truth
        cache_f = os.path.join(HERE, "cafa_expected_cache.json")
        cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
        by_idx = {s["sample_index"]: s for s in samples}
        nl = {}
        t0 = time.time()
        for n_done, si in enumerate(keep):
            s = by_idx[si]
            conds = {b["condition_id"]: b for b in s["conditions"]}
            for cid in (1, 2):
                key = f"{si}:{cid}"
                if key not in cache:
                    b = conds[cid]
                    exp, err = ground_truth(b["source_code"], stdin_of(s, b))
                    cache[key] = None if err is not None else len([l for l in exp.strip().splitlines() if l.strip()])
                nl[(si, cid)] = cache[key]
            if n_done % 300 == 0:
                print(f"   ...executed {n_done}/{len(keep)} programs ({time.time()-t0:.0f}s)", flush=True)
        json.dump(cache, open(cache_f, "w"))
        r = np.array([nl[(s, 1)] if nl[(s, 1)] is not None else -1 for s in keep])
        y = np.array([nl[(s, 2)] if nl[(s, 2)] is not None else -1 for s in keep])
        print("\n== expected-output length (lines): real C1 / synthetic C2")
        for name, v in (("real", r), ("synthetic", y)):
            print(f"   {name:10s} 1 line: {np.mean(v == 1):.3f}   2-3: {np.mean((v >= 2) & (v <= 3)):.3f}   4+: {np.mean(v >= 4):.3f}   (n={len(v)})")
        strata = {"ALL": np.ones(len(keep), bool),
                  "real single-line": r == 1, "real multi-line": r >= 2,
                  "synthetic single-line": y == 1, "synthetic multi-line": y >= 2,
                  "both multi-line": (r >= 2) & (y >= 2), "both single-line": (r == 1) & (y == 1)}
        print("\n== I x S inside strata (exploratory)")
        for name, m in strata.items():
            if m.sum() < 30:
                print(f"   {name:24s} n={m.sum()} (too few)")
                continue
            e = E[m][:, [iS]]
            bb = boot(e, a.boot)
            lo, hi = ci(bb[:, 0])
            print(f"   {name:24s} n={m.sum():5d}  IxS {fmt(e.mean())} [{fmt(lo)},{fmt(hi)}]  C1..C8 acc: " +
                  " ".join(f"{v:.2f}" for v in Y[m].mean(0)))

    # 4. popularity (submission count) test
    mdir = os.path.join(HERE, a.metadata)
    cnt, cnt_acc = {}, {}
    for pid in {pid_of[s] for s in keep}:
        f = os.path.join(mdir, f"{pid}.csv")
        if not os.path.exists(f):
            continue
        n_all = n_acc = 0
        with open(f, newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("language") == "Python":
                    n_all += 1
                    n_acc += row.get("status") == "Accepted"
        cnt[pid], cnt_acc[pid] = n_all, n_acc
    if not cnt:
        print(f"\n== popularity: no metadata found under {mdir}")
        return
    pids = [pid_of[s] for s in keep]
    pc = np.array([cnt.get(p, np.nan) for p in pids])
    ok = ~np.isnan(pc) & (pc > 0)
    print(f"\n== popularity (Python submissions per problem, CodeNet metadata); programs with a count: {ok.sum()}/{len(keep)}")
    print(f"   count quantiles (all Python rows) 10/50/90%: {np.percentile(pc[ok],[10,50,90]).astype(int).tolist()}")
    real0 = Y[:, [0, 2]].mean(1)          # real, original names (C1,C3)
    synth0 = Y[:, [1, 3]].mean(1)         # synthetic, original names (C2,C4)
    eIS = E[:, iS]
    # problem level (one program per problem in the confirmation set, so program == problem)
    for lab, v in (("real acc, orig names", real0), ("synthetic acc, orig names", synth0),
                   ("per-program I x S contrast", eIS), ("S gap (synth-real), orig names", synth0 - real0)):
        rho, p = spearman(np.log10(pc[ok]), v[ok])
        print(f"   Spearman(log10 count, {lab:32s}) rho={rho:+.3f} p={p:.3g}")
    qs = np.percentile(pc[ok], [100 / 3, 200 / 3])
    grp = np.where(pc <= qs[0], 0, np.where(pc <= qs[1], 1, 2))
    print("   tertiles of popularity (low/mid/high); I x S per tertile:")
    for g, nm in enumerate(["low", "mid", "high"]):
        m = ok & (grp == g)
        bb = boot(E[m][:, [iS]], a.boot)
        lo, hi = ci(bb[:, 0])
        print(f"   {nm:5s} n={m.sum():4d} count {int(pc[m].min())}-{int(pc[m].max())}  real {real0[m].mean():.3f}  synth {synth0[m].mean():.3f}  IxS {fmt(eIS[m].mean())} [{fmt(lo)},{fmt(hi)}]")
    print("   (exploratory; one program per problem so no clustering, but popularity is only a proxy for training-data exposure)")


# ----------------------------------------------------------------- rerun
def cmd_rerun(a):
    from scoring_harness import PROMPT_TEMPLATE, ground_truth, prompt_too_long
    from llama_cpp import Llama
    conds = {int(c) for c in a.conditions.split(",")}
    DEMOS = {"orig8": ("n = int(input())\nprint(n * 2)\n# Input:\n4\n# Output:\n8", "8"),
             "plus7": ("a = int(input())\nprint(a + 7)\n# Input:\n4\n# Output:\n11", "11"),
             "reverse": ("s = input()\nprint(s[::-1])\n# Input:\nabc\n# Output:\ncba", "cba"),
             "none": (None, None), "orig": (None, "10")}
    ORIG_DEMO = "# Program:\nn = int(input())\nprint(n * 2)\n# Input:\n5\n# Output:\n10\n\n"
    tmpl = PROMPT_TEMPLATE
    if a.demo != "orig":
        assert ORIG_DEMO in tmpl, "original demonstration not found in PROMPT_TEMPLATE"
        tmpl = tmpl.replace(ORIG_DEMO, "" if a.demo == "none" else "# Program:\n" + DEMOS[a.demo][0] + "\n\n")
    man = json.load(open(a.manifest))
    done = {(r["sample_index"], r["condition_id"]) for r in load_jsonl(a.out)}
    todo = [(s, b) for s in man["samples"] for b in s["conditions"] if b["condition_id"] in conds]
    if a.limit:
        todo = todo[: a.limit * len(conds)]
    print(f"{len(todo)} cells requested, {len(done)} already in {a.out}", flush=True)
    print(f"Loading {a.gguf} (n_ctx={a.n_ctx}) ...", flush=True)
    llm = Llama(model_path=a.gguf, n_gpu_layers=-1, n_ctx=a.n_ctx, verbose=False)
    t0 = time.time()
    n = 0
    with open(a.out, "a") as fo:
        for s, b in todo:
            si, cid = s["sample_index"], b["condition_id"]
            if (si, cid) in done:
                continue
            rec = {"sample_index": si, "condition_id": cid, "problem_id": s.get("problem_id"),
                   "gguf": os.path.basename(a.gguf), "n_ctx": a.n_ctx, "demo": a.demo, "demo_out": DEMOS[a.demo][1]}
            stdin = stdin_of(s, b)
            if b.get("status") != "ok" or not b.get("source_code") or not stdin:
                rec["status"] = "skip_build"
            else:
                exp, err = ground_truth(b["source_code"], stdin)
                if err is not None:
                    rec["status"] = "skip_groundtruth"
                else:
                    prompt = tmpl.format(code=b["source_code"].strip(), stdin=stdin.strip())
                    if prompt_too_long(llm, prompt, 64, a.n_ctx):
                        rec["status"] = "skipped_too_long"
                    else:
                        try:
                            out = llm(prompt, max_tokens=64, temperature=0.0,
                                      stop=["\n# Program:", "\n# Input:", "\n\n\n"])
                            pred = out["choices"][0]["text"]
                            from scoring_harness import normalize
                            rec.update(status="ok", prediction=pred, expected=exp, stdin=stdin,
                                       correct=bool(normalize(pred) == normalize(exp)))
                        except Exception as e:
                            rec["status"] = f"error: {type(e).__name__}: {str(e)[:120]}"
            fo.write(json.dumps(rec) + "\n")
            fo.flush()
            n += 1
            if n % 50 == 0:
                print(f"  ...{n}/{len(todo) - len(done)} cells ({time.time()-t0:.0f}s)", flush=True)
    print("done", flush=True)


# ----------------------------------------------------------------- classify
def _lines(t):
    return [l.strip() for l in t.strip().splitlines() if l.strip()]


_num = re.compile(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$")


def _isnum(x):
    return bool(_num.match(x))


def _squash(t):
    return re.sub(r"[^0-9A-Za-z.\-]+", "", t).lower()


CATS = ["empty", "echoes_input", "truncated_prefix", "extra_output", "wrong_line_count",
        "format_variant", "numeric_off_by_one", "numeric_wrong", "other_value"]


def categorize(pred, exp, stdin):
    p, e, si = _lines(pred), _lines(exp), set(_lines(stdin))
    if not p:
        return "empty"
    if all(l in si for l in p):
        return "echoes_input"
    if len(p) < len(e) and p == e[: len(p)]:
        return "truncated_prefix"
    if len(p) > len(e) and p[: len(e)] == e:
        return "extra_output"
    if len(p) != len(e):
        return "wrong_line_count"
    if _squash(" ".join(p)) == _squash(" ".join(e)):
        return "format_variant"
    diffs = [(x, y) for x, y in zip(p, e) if x != y]
    toks = [(x.split(), y.split()) for x, y in diffs]
    if all(len(tx) == len(ty) and all(_isnum(u) and _isnum(v) for u, v in zip(tx, ty) if u != v)
           for tx, ty in toks):
        mx = max((abs(float(u) - float(v)) for tx, ty in toks for u, v in zip(tx, ty) if u != v), default=0)
        return "numeric_off_by_one" if mx <= 1 else "numeric_wrong"
    return "other_value"


def cmd_classify(a):
    recs = load_jsonl(a.inp)
    A, Bc = a.a, a.b
    ok = {(r["sample_index"], r["condition_id"]): r for r in recs if r.get("status") == "ok"}
    st = collections.Counter(r.get("status") for r in recs)
    print(f"== {a.inp}: {len(recs)} records; status counts: {dict(st)}")
    if a.orig:
        o = load_orig(a.orig)
        both = [k for k in ok if k in o]
        agree = sum((1.0 if ok[k]["correct"] else 0.0) == o[k] for k in both)
        print(f"== reproduction vs original run ({a.orig}): {agree}/{len(both)} cells identical "
              f"({agree/max(1,len(both)):.4f}); original accuracy {np.mean([o[k] for k in both]):.4f}, rerun {np.mean([ok[k]['correct'] for k in both]):.4f}")
    summary = {}
    tab = {}
    for cid in (A, Bc):
        rs = [r for k, r in ok.items() if k[1] == cid]
        wrong = [r for r in rs if not r["correct"]]
        cats = collections.Counter(categorize(r["prediction"], r["expected"], r["stdin"]) for r in wrong)
        tab[cid] = (len(rs), len(wrong), cats)
        summary[str(cid)] = {"n": len(rs), "wrong": len(wrong), "acc": 1 - len(wrong) / max(1, len(rs)), "cats": dict(cats)}
    print(f"\n{'category':20s} " + "".join(f"C{c}: n(%wrong) [%all]".rjust(30) for c in (A, Bc)))
    for c in CATS:
        row = f"{c:20s} "
        for cid in (A, Bc):
            n, nw, cats = tab[cid]
            row += f"{cats.get(c,0):6d} ({100*cats.get(c,0)/max(1,nw):5.1f}%) [{100*cats.get(c,0)/max(1,n):5.1f}%]".rjust(30)
        print(row)
    print("TOTAL wrong".ljust(21) + "".join(f"{tab[c][1]:6d} of {tab[c][0]} (acc {1-tab[c][1]/max(1,tab[c][0]):.3f})".rjust(30) for c in (A, Bc)))
    pairs = [(ok[(s, A)]["correct"], ok[(s, Bc)]["correct"]) for (s, c) in ok if c == A and (s, Bc) in ok]
    t = collections.Counter(pairs)
    print(f"\npaired programs n={len(pairs)}: C{A} right/C{Bc} right={t[(True,True)]}  C{A} right/C{Bc} wrong={t[(True,False)]}  "
          f"C{A} wrong/C{Bc} right={t[(False,True)]}  both wrong={t[(False,False)]}")
    # does the wrong prediction copy a literal from the program text? (rough guide to 'pattern completion')
    rng = np.random.default_rng(0)
    ex = []
    for cid in (A, Bc):
        w = [r for k, r in ok.items() if k[1] == cid and not r["correct"]]
        for i in rng.permutation(len(w))[: a.examples]:
            r = w[i]
            ex.append({"cond": cid, "sample": r["sample_index"], "category": categorize(r["prediction"], r["expected"], r["stdin"]),
                       "predicted": r["prediction"].strip()[:120], "expected": r["expected"].strip()[:120]})
    base = os.path.splitext(a.inp)[0]
    json.dump({"summary": summary, "examples": ex}, open(base + "_taxonomy.json", "w"), indent=1)
    print(f"\nwrote {base}_taxonomy.json (summary + {len(ex)} random wrong answers; contains no program code)")


# ----------------------------------------------------------------- q8
def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def cmd_q8(a):
    q4 = load_orig(a.q4)
    q8 = rerun_scores(a.q8)
    cids = [1, 2, 5, 6]
    keep8, _ = matrix(q4)                         # complete cases of the paper (all 8 conditions at Q4)
    keep = [s for s in keep8 if all((s, c) in q8 for c in cids)]
    print(f"programs: complete-case at Q4 = {len(keep8)}; also scored (not skipped) at Q8_0 in C1,C2,C5,C6 = {len(keep)}")
    Y4 = np.array([[q4[(s, c)] for c in cids] for s in keep])
    Y8 = np.array([[q8[(s, c)] for c in cids] for s in keep])
    print(f"\n{'cond':5s} {'Q4 acc':>8s} {'Q8 acc':>8s} {'Q4 only':>8s} {'Q8 only':>8s} {'McNemar p':>10s}")
    for j, c in enumerate(cids):
        b = int(np.sum((Y4[:, j] == 1) & (Y8[:, j] == 0)))
        cc = int(np.sum((Y4[:, j] == 0) & (Y8[:, j] == 1)))
        print(f"C{c:<4d} {Y4[:,j].mean():8.3f} {Y8[:,j].mean():8.3f} {b:8d} {cc:8d} {mcnemar_exact(b,cc):10.4f}")
    # contrasts on the A=0 slice; columns are C1,C2,C5,C6
    def con(Y):
        y1, y2, y5, y6 = Y.T
        return np.stack([y2 - y1, y6 - y5, y5 - y1, y6 - y2, (y6 - y2) - (y5 - y1)], 1)
    names = ["S|orig-names", "S|obf-names", "I|real", "I|synth", "IxS"]
    E4, E8 = con(Y4), con(Y8)
    n = len(keep)
    rng = np.random.default_rng(0)
    b4 = np.empty((a.boot, 5)); b8 = np.empty((a.boot, 5))
    for s in range(0, a.boot, 250):
        m = min(250, a.boot - s)
        idx = rng.integers(0, n, (m, n))
        b4[s:s + m] = E4[idx].mean(1)
        b8[s:s + m] = E8[idx].mean(1)
    print("\nA=0 slice (conditions 1,2,5,6), program-level bootstrap, same resamples for Q4 and Q8")
    for j, nm in enumerate(names):
        l4, h4 = ci(b4[:, j]); l8, h8 = ci(b8[:, j]); ld, hd = ci(b8[:, j] - b4[:, j])
        print(f"  {nm:13s} Q4 {fmt(E4[:,j].mean())} [{fmt(l4)},{fmt(h4)}]   Q8 {fmt(E8[:,j].mean())} [{fmt(l8)},{fmt(h8)}]   Q8-Q4 {fmt(E8[:,j].mean()-E4[:,j].mean())} [{fmt(ld)},{fmt(hd)}]")
    sk = collections.Counter(r.get("status") for r in load_jsonl(a.q8))
    print(f"\nQ8 record status counts: {dict(sk)}")


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("checks")
    p.add_argument("--manifest", default="manifest_confirm.json")
    p.add_argument("--responses", default="responses_deepseek_confirm.json")
    p.add_argument("--metadata", default="Project_CodeNet/metadata")
    p.add_argument("--boot", type=int, default=10000)
    p.add_argument("--skip-strata", action="store_true", help="skip executing programs for output length")
    p.set_defaults(f=cmd_checks)
    p = sub.add_parser("rerun")
    p.add_argument("--manifest", default="manifest_confirm.json")
    p.add_argument("--gguf", required=True)
    p.add_argument("--conditions", default="1,2")
    p.add_argument("--out", required=True)
    p.add_argument("--n-ctx", type=int, default=8192)
    p.add_argument("--limit", type=int, default=0, help="only the first N programs (smoke test)")
    p.add_argument("--demo", default="orig", choices=["orig", "orig8", "plus7", "reverse", "none"], help="prompt demonstration: orig (the paper's), plus7, reverse, or none (zero-shot)")
    p.set_defaults(f=cmd_rerun)
    p = sub.add_parser("classify")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--orig", default=None, help="original responses_*.json, to verify the rerun reproduces it")
    p.add_argument("--a", type=int, default=1)
    p.add_argument("--b", type=int, default=2)
    p.add_argument("--examples", type=int, default=25)
    p.set_defaults(f=cmd_classify)
    p = sub.add_parser("q8")
    p.add_argument("--q4", default="responses_deepseek_confirm.json")
    p.add_argument("--q8", required=True)
    p.add_argument("--boot", type=int, default=10000)
    p.set_defaults(f=cmd_q8)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
