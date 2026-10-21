#!/usr/bin/env python3
"""r4_diag.py -- why do real programs with >= 3 reference solutions get no extra input? Re-runs the candidate loop and counts rejection reasons."""
import collections, json, random
import multiprocessing as mp
import r4_build_inputs as R
from g2_features import run_code

def diag(a):
    rec, cn = a
    conds = {c["condition_id"]: c for c in rec["conditions"]}; P = conds[1]["source_code"]; I0 = conds[1]["stdin_cases"][0]
    _, _, refs = R.references(cn, rec["problem_id"], P)
    rng = random.Random(R.seed_of("r4", rec["sample_index"])); why = collections.Counter()
    for att in range(R.MAX_ATT):
        cand = R.mutate(I0, rng, 1.0 if att % 2 == 0 else 0.3)
        if cand == I0: why["unchanged"] += 1; continue
        o, e = run_code(P, cand, timeout=R.TIMEOUT, mem_mb=R.MEM)
        if e: why["P_" + e] += 1; continue
        if not o.strip(): why["P_empty"] += 1; continue
        ran = agree = 0
        for r in refs:
            ro, re_ = run_code(r, cand, timeout=R.TIMEOUT, mem_mb=R.MEM)
            if re_ is None: ran += 1; agree += R.sn(ro) == R.sn(o)
        why["refs_all_error" if ran == 0 else "no_ref_agrees" if agree == 0 else "minority_agrees" if agree * 2 < ran else "ok"] += 1
    return rec["sample_index"], len(refs), dict(why), I0[:70].replace("\n", "\\n")

if __name__ == "__main__":
    r4 = json.load(open("r4_inputs.json"))["records"]
    bad = {r["sample_index"] for r in r4 if not r["extra"] and r["n_refs"] >= 3}
    m = json.load(open("manifest_confirm.json")); s = [x for x in (m["samples"] if isinstance(m, dict) else m) if x["sample_index"] in bad]
    with mp.Pool(40) as pool: res = pool.map(diag, [(x, "/data/workzone/PhD/Project_CodeNet") for x in s])
    tot = collections.Counter()
    dom = collections.Counter()
    for _, _, w, _ in res:
        tot.update(w); dom[max(w, key=w.get)] += 1
    print(len(res), "programs; rejection reasons over all attempts:", dict(tot)); print("dominant reason per program:", dict(dom))
    for r in res[:12]: print(r)
