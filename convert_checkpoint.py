#!/usr/bin/env python3
"""
convert_checkpoint.py -- rebuild per_sample_results from a harness checkpoint.

The checkpoint stores per_condition[cond][rep][program] (0/1). This writes the
same per_sample_results[program][cond] = [rep1, rep2, rep3] layout that
responses_qwen.json uses, so paired_effects.py can read it unchanged.

Usage:
    python3 convert_checkpoint.py responses.json.checkpoint responses_deepseek.json \
        --check responses.json
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoint")
    ap.add_argument("output")
    ap.add_argument("--check", help="responses.json whose response_matrix to verify against")
    a = ap.parse_args()

    d = json.load(open(a.checkpoint))
    pc = d["per_condition"]
    conds = sorted(pc, key=int)
    reps = len(pc[conds[0]])
    n = len(pc[conds[0]][0])
    for c in conds:
        assert len(pc[c]) == reps, f"cond {c}: {len(pc[c])} reps, expected {reps}"
        for r in range(reps):
            assert len(pc[c][r]) == n, f"cond {c} rep {r}: {len(pc[c][r])} programs, expected {n}"

    per_sample = {
        str(i): {c: [float(pc[c][r][i]) for r in range(reps)] for c in conds}
        for i in range(n)
    }

    # response_matrix: cond -> [mean accuracy for each rep]
    matrix = {c: [sum(pc[c][r]) / n for r in range(reps)] for c in conds}

    print(f"conditions={len(conds)} reps={reps} programs={n}")
    for c in conds:
        print(f"  C{c}: " + "  ".join(f"{x:.4f}" for x in matrix[c]))

    if a.check:
        ref = json.load(open(a.check))["response_matrix"]
        worst = 0.0
        for c in conds:
            for r in range(reps):
                worst = max(worst, abs(ref[c][r] - matrix[c][r]))
        status = "OK" if worst < 1e-9 else "MISMATCH -- do not use"
        print(f"\nmax |rebuilt - {a.check} response_matrix| = {worst:.2e}  [{status}]")

    json.dump(
        {
            "response_matrix": matrix,
            "per_sample_results": per_sample,
            "n_scored": d.get("n_scored"),
            "n_skipped": d.get("n_skipped"),
            "reps": reps,
            "rebuilt_from": a.checkpoint,
        },
        open(a.output, "w"),
    )
    print(f"wrote {a.output}")


if __name__ == "__main__":
    main()
