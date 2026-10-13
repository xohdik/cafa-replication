#!/usr/bin/env python3
"""
output_strata.py -- does accuracy depend on the SHAPE of the expected output?

Strata (from the expected output of the target program, executed exactly as the harness does):
  zero   : the output is exactly "0"
  empty  : no output
  multi  : more than one line (e.g. repeated lines from a loop)
  single : one line, anything else
Reported for the real condition C1 and the synthetic condition C2: how the programs split across
strata, then per model and stratum the main-run accuracy (program-level 95% CI). If a *.npc json from
no_program_control.py is given, the accuracy with ANOTHER program in the prompt is reported too.

Usage:
  python3 -W ignore output_strata.py --manifest manifest.json \
      responses_deepseek.json:DeepSeek:npc_deepseek.json responses_qwen.json:Qwen:npc_qwen.json
Run from the capa directory with paired_effects.py and scoring_harness.py importable.
"""
import argparse
import json
import os
import sys
import warnings
import numpy as np

warnings.filterwarnings("ignore", category=SyntaxWarning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "perturbations"))
from scoring_harness import ground_truth, normalize  # noqa: E402
from paired_effects import load  # noqa: E402

STRATA = ["zero", "empty", "multi", "single"]


def stratum(out):
    s = normalize(out)
    if s == "0":
        return "zero"
    if s == "":
        return "empty"
    return "multi" if "\n" in s else "single"


def expected_strata(manifest_path, pids):
    m = json.load(open(manifest_path))
    by = {}
    for s in m["samples"]:
        conds = {c["condition_id"]: c for c in s["conditions"]}
        row = {}
        for t in (1, 2):
            c = conds.get(t)
            cases = (c.get("stdin_cases") or s.get("stdin_cases")) if c else None
            if not c or not c.get("source_code") or not cases:
                continue
            out, err = ground_truth(c["source_code"], cases[0])
            if err is None:
                row[t] = stratum(out)
        by[str(s["sample_index"])] = row
    return {t: np.array([by.get(p, {}).get(t, "") for p in pids]) for t in (1, 2)}


def boot(v, rng, B=10000):
    idx = rng.integers(0, len(v), (B, len(v)))
    b = v[idx].mean(1)
    return v.mean(), *np.percentile(b, [2.5, 97.5])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+", help="responses.json:Label[:npc.json]")
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    first = a.specs[0].split(":")[0]
    pids, _ = load(first)
    S = expected_strata(a.manifest, pids)

    print("Share of programs by expected-output stratum")
    print(f"{'':<10}" + "".join(f"{k:>10}" for k in STRATA))
    for t, nm in ((1, "real C1"), (2, "synth C2")):
        print(f"{nm:<10}" + "".join(f"{(S[t] == k).mean():>10.3f}" for k in STRATA))

    for spec in a.specs:
        parts = spec.split(":")
        path, label = parts[0], (parts[1] if len(parts) > 1 else parts[0])
        pids2, A = load(path)
        assert pids2 == pids, "program ids differ between response files"
        P = A.mean(2)
        npc = json.load(open(parts[2]))["results"] if len(parts) > 2 else None
        print("\n" + "=" * 86)
        print(label)
        print("=" * 86)
        for t, nm in ((1, "real C1"), (2, "synthetic C2")):
            print(f"\n {nm}: main-run accuracy by expected-output stratum")
            for k in STRATA:
                mk = S[t] == k
                n = int(mk.sum())
                if n < 5:
                    print(f"   {k:<7} n={n:4d}  (too few)")
                    continue
                m, lo, hi = boot(P[mk, t - 1], rng)
                line = f"   {k:<7} n={n:4d}  acc {m:.3f} [{lo:.3f}, {hi:.3f}]"
                if npc:
                    vals = [npc[p][str(t)]["other"] for p in np.array(pids)[mk] if p in npc and npc[p][str(t)]["other"] is not None]
                    if len(vals) >= 5:
                        line += f"   | other-program acc {np.mean(vals):.3f}"
                print(line)


if __name__ == "__main__":
    main()
