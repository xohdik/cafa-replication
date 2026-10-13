"""
Converts the EMSE SiameseGAT corpus (pairs_codenet_python.json -- a JSON
array of {"pair_id", "correct_code", "buggy_code"} objects) into the .jsonl
format rq4_batch_check.py expects: one {"source_code": ...} object per line.

WHY ONE FIELD PER PAIR, NOT BOTH: correct_code and buggy_code in a bug-fix
pair are near-identical by construction (that's the whole point of the
corpus). Including both would flood the RQ4 manipulation-check pool with
correlated near-duplicates, biasing the distributional stats -- the mean/
median/stdev would partly be measuring "the same code twice," not
independent samples. Default is correct_code only; --field lets you
override, and --field both is available but prints a warning, since it's
almost certainly not what you want for this specific check.

WHY SUBSAMPLE TO ~500: RESEARCH_PLAN.md Section 5.2 specifies "~500 held-out
code samples" for the manipulation check -- this is a validation
prerequisite, not the real sweep, so there's no reason to burn all 10,386
pairs on it. --n overrides if you want a different size.

Usage:
    python3 convert_emse_to_rq4.py \\
        --input PATH/TO/pairs_codenet_python.json \\
        --output rq4_samples.jsonl \\
        --n 500 --field correct --seed 0
"""
import argparse
import json
import random


def convert(input_path: str, output_path: str, n: int, field: str, seed: int) -> dict:
    with open(input_path) as f:
        pairs = json.load(f)

    if not isinstance(pairs, list):
        raise ValueError(f"Expected a JSON array at {input_path}, got {type(pairs).__name__}. "
                          "If the real schema wraps the array in an object (e.g. {'pairs': [...]}), "
                          "adjust the json.load(f) line above accordingly.")

    rng = random.Random(seed)

    if field == "both":
        print("WARNING: --field both includes both correct_code and buggy_code from "
              "the same pairs -- these are near-duplicates by construction and will "
              "bias the RQ4 distributional stats. Proceeding because you asked for it "
              "explicitly, but this is almost certainly not what you want.")
        records = []
        for p in pairs:
            if p.get("correct_code"):
                records.append({"source_code": p["correct_code"], "pair_id": p.get("pair_id"), "field": "correct_code"})
            if p.get("buggy_code"):
                records.append({"source_code": p["buggy_code"], "pair_id": p.get("pair_id"), "field": "buggy_code"})
    else:
        key = "correct_code" if field == "correct" else "buggy_code"
        records = [
            {"source_code": p[key], "pair_id": p.get("pair_id"), "field": key}
            for p in pairs if p.get(key)
        ]

    n_available = len(records)
    if n < n_available:
        records = rng.sample(records, n)

    with open(output_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    return {"n_pairs_in_source": len(pairs), "n_records_available": n_available,
            "n_written": len(records), "field": field, "output_path": output_path}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None, help="Path to pairs_codenet_python.json")
    parser.add_argument("--output", default="rq4_samples.jsonl")
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--field", choices=["correct", "buggy", "both"], default="correct")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--self-test", action="store_true",
                         help="Run against a small built-in mock fixture instead of --input, "
                              "to verify the converter logic without touching real data.")
    args = parser.parse_args()

    if args.self_test:
        import tempfile
        import os
        mock_pairs = [
            {"pair_id": f"p{i}",
             "correct_code": f"def f{i}(x):\n    return x + {i}",
             "buggy_code": f"def f{i}(x):\n    return x - {i}"}
            for i in range(20)
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(mock_pairs, f)
            mock_path = f.name
        try:
            stats = convert(mock_path, "/tmp/rq4_selftest.jsonl", n=10, field="correct", seed=0)
            print("Self-test stats:", json.dumps(stats, indent=2))
            with open("/tmp/rq4_selftest.jsonl") as f:
                lines = f.readlines()
            assert len(lines) == 10, f"expected 10 lines, got {len(lines)}"
            for line in lines:
                obj = json.loads(line)
                assert "source_code" in obj and obj["source_code"].startswith("def f")
            print(f"Self-test PASSED: {len(lines)} valid JSONL lines written, "
                  f"each with a source_code field.")
        finally:
            os.unlink(mock_path)
    else:
        if not args.input:
            parser.error("--input is required (or use --self-test)")
        stats = convert(args.input, args.output, args.n, args.field, args.seed)
        print(json.dumps(stats, indent=2))
        print(f"\nNext: python3 rq4_batch_check.py --samples {args.output}")