"""
Diagnose WHY X4 synthesis misses tolerance on real data, rather than guess
a second time. A synthetic mock pool showed 1% miss rate after the
straight-line-template fix; the real corpus showed 71%. Those are not the
same problem at different severity -- something about real CodeNet
complexity profiles is outside what the templates can represent at all,
and this script measures what, instead of assuming.

Usage:
    python3 diagnose_x4_synthesis.py --samples rq4_samples_verified.jsonl --limit 300
"""
import argparse
import json
import os
import statistics
import sys
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from synthesize import complexity_profile, generate_synthetic_script


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--tolerance", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import random
    rng = random.Random(args.seed)

    samples = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    samples = [s for s in samples if s.get("stdin_cases")][:args.limit]

    targets = []
    misses = []
    for s in samples:
        try:
            t = complexity_profile(s["source_code"])
        except SyntaxError:
            continue
        targets.append(t)
        code, achieved, dist = generate_synthetic_script(t, rng=rng)
        if dist > args.tolerance:
            misses.append((t, achieved, dist, s.get("pair_id") or s.get("repo_id")))

    def stats(vals):
        vals = sorted(vals)
        n = len(vals)
        return {"n": n, "min": vals[0], "median": vals[n // 2],
                "mean": statistics.mean(vals), "p90": vals[int(0.9 * (n - 1))],
                "max": vals[-1]}

    print("=" * 70)
    print("1. WHAT DOES REAL CODE ACTUALLY LOOK LIKE? (target profiles)")
    print("=" * 70)
    for dim, vals in [("cyclomatic", [t.cyclomatic for t in targets]),
                       ("lines", [t.lines for t in targets]),
                       ("max_depth", [t.max_depth for t in targets])]:
        s = stats(vals)
        print(f"  {dim:<12} min={s['min']:<4} median={s['median']:<5} "
              f"mean={s['mean']:<6.1f} p90={s['p90']:<5} max={s['max']}")

    print()
    print("=" * 70)
    print(f"2. MISSES: {len(misses)}/{len(targets)} "
          f"({len(misses)/len(targets):.1%}) exceed tolerance {args.tolerance}")
    print("=" * 70)
    if misses:
        for dim, idx in [("cyclomatic", 0), ("lines", 1), ("max_depth", 2)]:
            gaps = [abs(getattr(t, dim) - getattr(a, dim)) for t, a, d, pid in misses]
            s = stats(gaps)
            print(f"  |target-achieved| {dim:<12} median={s['median']:<5} "
                  f"mean={s['mean']:<6.1f} max={s['max']}")

        print("\n  Which dimension dominates the miss? (largest abs gap per miss)")
        from collections import Counter
        dominant = Counter()
        for t, a, d, pid in misses:
            gaps = {"cyclomatic": abs(t.cyclomatic - a.cyclomatic),
                    "lines": abs(t.lines - a.lines),
                    "max_depth": abs(t.max_depth - a.max_depth)}
            dominant[max(gaps, key=gaps.get)] += 1
        for dim, n in dominant.most_common():
            print(f"    {dim:<12} {n:4d} ({n/len(misses):.1%})")

        print("\n  Worst 5 misses:")
        worst = sorted(misses, key=lambda x: -x[2])[:5]
        for t, a, d, pid in worst:
            print(f"    {pid}: target(cyc={t.cyclomatic},lines={t.lines},depth={t.max_depth})"
                  f" achieved(cyc={a.cyclomatic},lines={a.lines},depth={a.max_depth})"
                  f" dist={d:.3f}")

    print()
    print("=" * 70)
    print("3. WHAT CAN THE CURRENT TEMPLATES ACTUALLY PRODUCE?")
    print("=" * 70)
    achieved_cyc, achieved_lines, achieved_depth = [], [], []
    for _ in range(300):
        # probe the templates' own achievable range independent of any target,
        # by feeding them a spread of targets and recording raw output shape
        probe_targets = [complexity_profile("n=1\nprint(n)"),
                          complexity_profile("for i in range(9):\n if i:\n  print(i)")]
        import random as _r
        t = _r.choice(probe_targets)
        code, achieved, dist = generate_synthetic_script(t, rng=rng)
        achieved_cyc.append(achieved.cyclomatic)
        achieved_lines.append(achieved.lines)
        achieved_depth.append(achieved.max_depth)
    for dim, vals in [("cyclomatic", achieved_cyc), ("lines", achieved_lines),
                       ("max_depth", achieved_depth)]:
        s = stats(vals)
        print(f"  achievable {dim:<12} min={s['min']:<4} max={s['max']}")

    print()
    print("=" * 70)
    print("INTERPRETATION")
    print("=" * 70)
    print("  Compare section 1's real-corpus range against section 3's")
    print("  achievable range. If real targets (esp. lines, cyclomatic) commonly")
    print("  exceed what the templates can produce at max parameters, this is a")
    print("  RANGE problem: the templates need restructuring (loops that scale")
    print("  with target size, more varied branch/statement generation), not")
    print("  just more search attempts. If targets are within range but still")
    print("  missed, it's a SEARCH problem: max_tries or the parameter-to-")
    print("  profile mapping needs work. Section 2's dominant-dimension count")
    print("  says which axis (lines vs cyclomatic vs depth) to fix first.")


if __name__ == "__main__":
    main()