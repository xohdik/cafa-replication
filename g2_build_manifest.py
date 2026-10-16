#!/usr/bin/env python3
"""g2_build_manifest.py -- turn the frozen G2 programs into a scoring manifest with the paper's own treatment code.

Reads g2_base.json (Gate A/B passed, committed before any scoring) and builds conditions 2, 4, 6 and 8 (program source S = generator,
identifiers I and AST shuffle A varied: cid - 1 = 4*I + 2*A + S) for every sample, by calling orchestrator.build_condition with the same
operators, the same order (identifiers, then shuffle, then ast.unparse normalisation) and the same hard eligibility gate as the real conditions.
A sample enters only if it can receive every treatment; the rest are listed under "excluded" with the reason (no silent drops).
The shuffle is verified on all three G2 stdin cases (the real conditions verified on one). Run from the repo directory, env cafa."""
import argparse, collections, hashlib, json, random, sys
import multiprocessing as mp

CONDS = {2: ("original", "original"), 4: ("original", "randomized_valid_ast"),
         6: ("obfuscated_renamed", "original"), 8: ("obfuscated_renamed", "randomized_valid_ast")}


def shuffle_seed(idx):
    return int(hashlib.sha256(f"g2-shuffle-{idx}".encode()).hexdigest()[:8], 16)


def work(task):
    rec, problem_id = task
    from orchestrator import build_condition, check_sample_eligibility
    idx = rec["sample_index"]
    base = {"source_code": rec["source_code"], "func_name": None, "test_inputs": None, "stdin_cases": rec["stdin_cases"], "repo_id": None}
    cfg = {"rng": random.Random(shuffle_seed(idx)), "shuffle_seed": shuffle_seed(idx), "verify_x3": True, "verify_x2": True, "normalize_baseline": True}
    ok, why = check_sample_eligibility(base, cfg)
    if not ok:
        return {"sample_index": idx, "excluded": why}
    built = []
    for cid, (ident, struct) in CONDS.items():
        cond = {"condition_id": cid, "identifiers": ident, "ast_structure": struct, "syntheticity": "real_world_code"}
        b = build_condition(base, cond, cfg)
        if b.get("status") != "ok" or not b.get("source_code"):
            return {"sample_index": idx, "excluded": f"condition {cid} failed: " + json.dumps(b.get("log", {}).get("steps", [])[-1:])}
        built.append(b)
    return {"sample_index": idx, "problem_id": problem_id, "tol_level": rec.get("tol_level"), "target": rec.get("target"), "achieved": rec.get("achieved"),
            "stdin_cases": rec["stdin_cases"], "conditions": built}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--g2", default="g2_base.json"); ap.add_argument("--real-manifest", default="manifest_confirm.json")
    ap.add_argument("--out", default="manifest_g2.json"); ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--prereg-commit", default="")
    a = ap.parse_args()
    g2 = json.load(open(a.g2)); real = json.load(open(a.real_manifest))
    pid = {s["sample_index"]: s.get("problem_id") for s in real["samples"]}
    recs = [r for r in g2["samples"] if r["status"] == "ok"]
    if a.limit: recs = recs[:a.limit]
    tasks = [(r, pid.get(r["sample_index"])) for r in recs]
    out, done = [], 0
    with mp.Pool(a.jobs) as pool:
        for r in pool.imap(work, tasks, chunksize=4):
            out.append(r); done += 1
            if done % 100 == 0: print(done, "done", file=sys.stderr)
    ok = [r for r in out if "conditions" in r]; ex = [r for r in out if "excluded" in r]
    reasons = collections.Counter(r["excluded"].split(":")[0][:80] for r in ex)
    x3 = collections.Counter(); changed = collections.Counter(); n_cond = 0
    for r in ok:
        c = {b["condition_id"]: b for b in r["conditions"]}
        for cid in (4, 8):
            st = next((s for s in c[cid]["log"]["steps"] if s["op"] == "ast_structure"), {})
            x3["reverted" if st.get("reverted") else "shuffled"] += 1
        changed["A_changed(4 vs 2)"] += c[4]["source_code"] != c[2]["source_code"]
        changed["A_changed(8 vs 6)"] += c[8]["source_code"] != c[6]["source_code"]
        changed["I_changed(6 vs 2)"] += c[6]["source_code"] != c[2]["source_code"]
        n_cond += len(c)
    man = {"samples": ok, "excluded": [{"sample_index": r["sample_index"], "reason": r["excluded"]} for r in ex],
           "summary": {"n_samples_submitted": len(recs), "n_samples_eligible": len(ok), "n_samples_excluded": len(ex), "n_conditions_total": 4 * len(recs),
                       "n_conditions_ok": n_cond, "n_conditions_failed": 4 * len(recs) - n_cond, "n_x3_reverted": x3["reverted"], "n_x3_skipped_unverifiable": 0,
                       "n_x3_shuffled": x3["shuffled"], "excluded_reasons": dict(reasons), "effective_changes": dict(changed)},
           "g2": {"source": a.g2, "source_sha256": hashlib.sha256(open(a.g2, "rb").read()).hexdigest(), "real_manifest_sha256": g2.get("manifest_sha256"),
                  "seed": g2.get("seed"), "conditions_built": sorted(CONDS), "prereg_commit": a.prereg_commit}}
    json.dump(man, open(a.out, "w"))
    print(json.dumps(man["summary"], indent=1)); print("manifest sha256:", hashlib.sha256(open(a.out, "rb").read()).hexdigest())


if __name__ == "__main__":
    main()
