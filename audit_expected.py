#!/usr/bin/env python3
"""
audit_expected.py -- does the scored program print the scored expected output?  (CPU only)

For every record of a rerun jsonl (fields sample_index, condition_id, status, stdin, expected) it executes the program of that
condition from the manifest on that record's stdin and compares its output with the record's `expected` text, using the scoring
rule of the paper (trailing whitespace removed from every line and from the whole text). It is a check of the ground truth that
every model was scored against, independent of any model: expected output == output of the program that was shown to the model.

Usage:  python3 audit_expected.py --manifest manifest_confirm.json --rerun rerun_q7_q4.jsonl [--workers 8] [--timeout 10]
"""
import argparse, json, os, subprocess, sys, tempfile, collections
from concurrent.futures import ThreadPoolExecutor


def norm(s):
    return "\n".join(l.rstrip() for l in (s or "").splitlines()).rstrip()


def run(code, stdin, timeout):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "prog.py"); open(p, "w", encoding="utf8").write(code)
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        try:
            r = subprocess.run([sys.executable, p], input=stdin, capture_output=True, text=True, timeout=timeout, cwd=d, env=env)
            return r.returncode, norm(r.stdout), r.stderr.strip().splitlines()[-1][:100] if r.returncode and r.stderr.strip() else ""
        except subprocess.TimeoutExpired:
            return "timeout", "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True); ap.add_argument("--rerun", required=True)
    ap.add_argument("--workers", type=int, default=8); ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args()
    code = {}
    for s in json.load(open(a.manifest))["samples"]:
        for c in s["conditions"]:
            code[(s["sample_index"], c["condition_id"])] = c["source_code"]
    recs = [json.loads(l) for l in open(a.rerun) if l.strip()]
    recs = [r for r in recs if r.get("status") == "ok"]

    def one(r):
        rc, out, err = run(code[(r["sample_index"], r["condition_id"])], r["stdin"], a.timeout)
        return r, rc, out, err
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(one, recs))
    tot, bad = collections.Counter(), []
    for r, rc, out, err in res:
        c = r["condition_id"]; tot[c] += 1
        if rc != 0 or out != norm(r["expected"]):
            tot[(c, "bad")] += 1
            bad.append((r["sample_index"], c, rc, err, out[:60], norm(r["expected"])[:60]))
    for c in sorted(k for k in tot if isinstance(k, int)):
        print(f"condition {c}: {tot[c]} records, expected output not reproduced: {tot[(c, 'bad')]}")
    for b in bad[:25]: print("  ", b)
    print(f"total not reproduced: {len(bad)} of {len(res)}")


if __name__ == "__main__":
    main()
