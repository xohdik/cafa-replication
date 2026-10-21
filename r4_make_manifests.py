#!/usr/bin/env python3
"""r4_make_manifests.py -- manifest_r4_x1.json / manifest_r4_x2.json: conditions 1 and 5 of each program that has the k-th extra input, with that input as the stdin case."""
import json
r4 = {r["sample_index"]: r for r in json.load(open("r4_inputs.json"))["records"]}
m = json.load(open("manifest_confirm.json")); S = m["samples"] if isinstance(m, dict) else m
for k in (0, 1):
    out = []
    for s in S:
        r = r4[s["sample_index"]]
        if len(r["extra"]) <= k: continue
        conds = []
        for b in s["conditions"]:
            if b["condition_id"] in (1, 5):
                b2 = dict(b); b2["stdin_cases"] = [r["extra"][k]["stdin"]]; conds.append(b2)
        out.append({"sample_index": s["sample_index"], "problem_id": s["problem_id"], "conditions": conds})
    json.dump({"samples": out, "source": "r4_inputs.json", "extra_index": k}, open(f"manifest_r4_x{k + 1}.json", "w"))
    print(f"manifest_r4_x{k + 1}.json: {len(out)} programs, {2 * len(out)} cells per model")
