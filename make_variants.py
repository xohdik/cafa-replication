#!/usr/bin/env python3
"""
make_variants.py -- build the two generator-variant manifests. Only condition 2 (generator programs, original names) changes.
  n5    : every generator program is run on n = 5 (stdin "5\\n1 2 3 4 5\\n") instead of the fixed n = 3 stdin of the manifest.
  nopad : the dead `_padK = V` assignments are deleted (a `pass` is inserted where that would leave a block empty).
Every changed program is re-verified by execution (it must run; for nopad its output must equal the original program's
output on the original stdin). Programs that fail verification get status "skip_var" and are left out of the rerun.
Usage (from capa/, cafa env):  python3 make_variants.py [manifest_confirm.json]
Writes manifest_var_n5.json, manifest_var_nopad.json and variants_report.json.
"""
import copy
import json
import re
import sys

from scoring_harness import ground_truth, normalize

PAD = re.compile(r"^\s*_pad\d+\s*=\s*\d+\s*$")
NEW_STDIN = "5\n1 2 3 4 5\n"


def stdin_of(s, b):
    cases = b.get("stdin_cases") or s.get("stdin_cases")
    return cases[0] if cases else None


def strip_pads(code):
    out = [l for l in code.split("\n") if not PAD.match(l)]
    fixed = []
    for i, l in enumerate(out):
        fixed.append(l)
        if l.rstrip().endswith(":"):
            ind = len(l) - len(l.lstrip())
            nxt = next((m for m in out[i + 1:] if m.strip()), None)
            if nxt is None or len(nxt) - len(nxt.lstrip()) <= ind:
                fixed.append(" " * (ind + 4) + "pass")
    return "\n".join(fixed)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "manifest_confirm.json"
    man = json.load(open(path))
    rep = {"n5": {"programs": 0, "ok": 0, "failed": 0, "not_starting_with_n_input": 0},
           "nopad": {"programs": 0, "had_pads": 0, "no_pads": 0, "verified": 0, "failed": 0, "lines_before": 0, "lines_after": 0}}
    out = {"n5": copy.deepcopy(man), "nopad": copy.deepcopy(man)}
    for v in out:
        for s in out[v]["samples"]:
            for b in s["conditions"]:
                if b["condition_id"] != 2 or b.get("status") != "ok" or not b.get("source_code"):
                    continue
                code, stdin0 = b["source_code"], stdin_of(s, b)
                if v == "n5":
                    r = rep["n5"]; r["programs"] += 1
                    if not code.lstrip().startswith("n = int(input())"):
                        r["not_starting_with_n_input"] += 1
                    exp, err = ground_truth(code, NEW_STDIN)
                    if err is not None:
                        b["status"] = "skip_var"; r["failed"] += 1
                    else:
                        b["stdin_cases"] = [NEW_STDIN]; r["ok"] += 1
                else:
                    r = rep["nopad"]; r["programs"] += 1
                    new = strip_pads(code)
                    r["lines_before"] += len(code.split("\n")); r["lines_after"] += len(new.split("\n"))
                    if new == code:
                        r["no_pads"] += 1; continue
                    r["had_pads"] += 1
                    e0, err0 = ground_truth(code, stdin0)
                    e1, err1 = ground_truth(new, stdin0)
                    if err0 is None and err1 is None and normalize(e0) == normalize(e1):
                        b["source_code"] = new; r["verified"] += 1
                    else:
                        b["status"] = "skip_var"; r["failed"] += 1
    for v in out:
        json.dump(out[v], open(f"manifest_var_{v}.json", "w"))
    r = rep["nopad"]
    if r["programs"]:
        r["mean_lines_before"] = round(r["lines_before"] / r["programs"], 2); r["mean_lines_after"] = round(r["lines_after"] / r["programs"], 2)
    json.dump(rep, open("variants_report.json", "w"), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
