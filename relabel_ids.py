#!/usr/bin/env python3
"""
relabel_ids.py -- give a converted responses file the original program ids.

convert_checkpoint.py numbers programs 0..N-1 by list position. The harness
actually scored only the ELIGIBLE programs, in ascending original-id order, and
records which ids those were in the checkpoint's completed_pairs
([program_id, condition]). This maps position -> original id so the file pairs
with responses_qwen.json (which uses original ids).

Usage:
    python3 relabel_ids.py responses_deepseek.json responses.json.checkpoint \
        --expect responses_qwen.json
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("converted")
    ap.add_argument("checkpoint")
    ap.add_argument("--expect", help="another responses file whose ids must match exactly")
    a = ap.parse_args()

    d = json.load(open(a.converted))
    ps = d["per_sample_results"]
    ids = sorted({p[0] for p in json.load(open(a.checkpoint))["completed_pairs"]})

    if d.get("ids_relabelled"):
        raise SystemExit("Already relabelled; refusing to map twice.")
    if len(ids) != len(ps):
        raise SystemExit(f"{len(ids)} ids in checkpoint vs {len(ps)} programs in file; cannot map.")

    d["per_sample_results"] = {str(ids[int(k)]): v for k, v in ps.items()}
    d["ids_relabelled"] = True

    if a.expect:
        other = set(json.load(open(a.expect))["per_sample_results"])
        mine = set(d["per_sample_results"])
        print(f"ids identical to {a.expect}: {mine == other}")
        if mine != other:
            raise SystemExit("Id sets differ; not writing.")

    json.dump(d, open(a.converted, "w"))
    print(f"relabelled {len(ids)} programs (ids {ids[0]}..{ids[-1]}) in {a.converted}")


if __name__ == "__main__":
    main()
