"""
Stratified re-scoring for the loop-depth confound found in the syntheticity
factor (check_iteration_depth.py showed accuracy collapsing to 0.000 the
moment a nested loop appears in the synthetic condition -- present in
~30% of the real corpus's synthetic-condition samples).

This does NOT reanalyze responses.json -- that file only ever stored
condition-level aggregates, never per-sample results, so there was nothing
to subset. This runs a smaller, TARGETED sweep instead: two capped-size
sample buckets (shallow loop depth, deep loop depth), all 8 conditions each,
reusing the same scoring_harness.run() already verified correct (checkpoint/
resume, oversized-prompt handling, atomic per-pair commits) rather than
duplicating that logic.

Cost: with --per-bucket 60 (default), 60 samples x 8 conditions x 3 reps x 2
buckets = 2880 scoring calls, versus 11520 for the full sweep -- about 25%
of the cost, roughly 15-20 minutes at the previously observed ~2.8/s rate.

Usage:
    python3 stratified_rescore.py --manifest manifest.json \\
        --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --per-bucket 60

Then decompose each bucket separately with the existing tool:
    python3 decompose.py --responses responses_shallow.json
    python3 decompose.py --responses responses_deep.json
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

import scoring_harness as sh


def bucket_samples(manifest: dict, depth_threshold: int = 2):
    """Loop-depth proxy: count of 'for i_' occurrences in condition 2's
    (Original, Original, Synthetic) source code. Same proxy already used
    and confirmed informative by check_iteration_depth.py."""
    shallow, deep = [], []
    for s in manifest.get("samples", []):
        c2 = next((c for c in s.get("conditions", []) if c["condition_id"] == 2), None)
        if not c2 or c2.get("status") != "ok" or not c2.get("source_code"):
            continue
        depth = c2["source_code"].count("for i_")
        (deep if depth >= depth_threshold else shallow).append(s)
    return shallow, deep


def filtered_manifest(manifest: dict, samples: list) -> dict:
    m = dict(manifest)
    m["samples"] = samples
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--per-bucket", type=int, default=60,
                    help="Max samples per depth bucket. Larger = tighter "
                         "bootstrap CI, proportionally more GPU time.")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--depth-threshold", type=int, default=2,
                     help="Loop-nesting count at/above which a sample is "
                          "'deep' rather than 'shallow'. 2 matches where "
                          "check_iteration_depth.py showed accuracy collapse.")
    ap.add_argument("--n-ctx", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    manifest = json.load(open(args.manifest))
    shallow, deep = bucket_samples(manifest, args.depth_threshold)
    print(f"Available: {len(shallow)} shallow (depth<{args.depth_threshold}), "
          f"{len(deep)} deep (depth>={args.depth_threshold})")

    rng = random.Random(args.seed)
    rng.shuffle(shallow)
    rng.shuffle(deep)
    shallow = shallow[:args.per_bucket]
    deep = deep[:args.per_bucket]
    print(f"Using: {len(shallow)} shallow, {len(deep)} deep "
          f"(capped at --per-bucket {args.per_bucket})")

    if len(shallow) < 10 or len(deep) < 10:
        print("WARNING: fewer than 10 samples in a bucket -- the bootstrap "
              "CI for that bucket will be wide. Proceeding anyway.")

    from llama_cpp import Llama
    print(f"\nLoading {args.gguf} ...")
    llm = Llama(model_path=args.gguf, n_gpu_layers=-1, n_ctx=args.n_ctx, verbose=False)

    for label, samples in [("shallow", shallow), ("deep", deep)]:
        if not samples:
            print(f"\nSkipping {label} bucket -- no eligible samples.")
            continue
        out_path = f"responses_{label}.json"
        print(f"\n{'='*66}\nSCORING {label.upper()} bucket ({len(samples)} samples)\n{'='*66}")
        sub_manifest = filtered_manifest(manifest, samples)
        result = sh.run(sub_manifest, llm, reps=args.reps, out_path=out_path,
                         n_ctx=args.n_ctx, progress_every=20)
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"scored={result['n_scored']} skipped={result['n_skipped']} "
              f"elapsed={result['elapsed_seconds']:.0f}s")
        print(f"Written to {out_path}")

    print(f"\n{'='*66}")
    print("Next: decompose each bucket separately")
    print(f"{'='*66}")
    print("  python3 decompose.py --responses responses_shallow.json")
    print("  python3 decompose.py --responses responses_deep.json")
    print()
    print("Compare the two S_i(syntheticity) values directly -- a large gap")
    print("between them confirms loop-depth (not artificiality per se) as")
    print("the dominant driver, matching check_iteration_depth.py's finding.")


if __name__ == "__main__":
    main()