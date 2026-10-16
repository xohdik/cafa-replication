#!/usr/bin/env python3
"""g2_audit.py -- Gate C: execution audit of the G2 manifest (PREREG_G2.md).
Every program of every built condition runs on all three stdin cases; the four conditions of a sample must print identical output on each case.
Also reports how many treatments actually changed the code (a shuffle that reverted, or an identifier pass that renamed nothing, is not a treatment)."""
import argparse, collections, hashlib, json, sys
import multiprocessing as mp
from g2_features import run_code


def work(rec):
    out = {"sample_index": rec["sample_index"], "fail": [], "mismatch": [], "chars": 0}
    conds = {b["condition_id"]: b for b in rec["conditions"]}
    for ci, stdin in enumerate(rec["stdin_cases"]):
        outs = {}
        for cid, b in conds.items():
            o, err = run_code(b["source_code"], stdin, timeout=10.0, mem_mb=4096)
            if err: out["fail"].append([cid, ci, err])
            outs[cid] = o
        vals = {o for o in outs.values() if o is not None}
        if len(vals) > 1: out["mismatch"].append(ci)
    out["chars"] = max(len(b["source_code"]) for b in conds.values())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest_g2.json"); ap.add_argument("--out", default="g2_audit")
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    man = json.load(open(a.manifest))
    with mp.Pool(a.jobs) as pool:
        res = list(pool.imap(work, man["samples"], chunksize=4))
    nf = sum(1 for r in res if r["fail"]); nm = sum(1 for r in res if r["mismatch"])
    ch = sorted(r["chars"] for r in res)
    summ = man["summary"]
    rep = {"manifest_sha256": hashlib.sha256(open(a.manifest, "rb").read()).hexdigest(), "n_samples": len(res), "n_excluded": summ["n_samples_excluded"],
           "excluded_reasons": summ.get("excluded_reasons"), "samples_with_run_failure": nf, "samples_with_output_mismatch": nm,
           "x3": {"shuffled": summ["n_x3_shuffled"], "reverted": summ["n_x3_reverted"]}, "effective_changes": summ.get("effective_changes"),
           "chars_median_max": [ch[len(ch) // 2], ch[-1]] if ch else None, "gate_C_pass": nf == 0 and nm == 0,
           "examples_failed": [r for r in res if r["fail"] or r["mismatch"]][:10]}
    json.dump(rep, open(a.out + ".json", "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
