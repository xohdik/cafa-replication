#!/usr/bin/env python3
"""
audit_final.py -- final execution audit of a scored manifest (CPU only, no GPU, no model).

For every sample in the manifest it executes the program of each of the eight conditions on that condition's stdin cases and checks
the property the design relies on:
    real group       conditions 1, 3, 5, 7   (original / shuffled / obfuscated / both)  must print the same output
    generator group  conditions 2, 4, 6, 8                                                must print the same output
(the two groups are NOT compared with each other: a generator program computes something else by design).
It reports, per condition and per group: programs executed, non-zero exit, timeouts, and groups whose outputs differ,
and writes every disagreeing sample to --out (JSON) so each can be inspected. Exit status is 1 if any scored sample disagrees.

Output equality is exact after removing trailing whitespace from every line and from the whole text (the scoring rule of the paper).
The programs are public CodeNet code: run this inside the same sandbox/container you use for the pipeline, not as a privileged user.

Usage:
    python3 audit_final.py --manifest manifest_confirm.json --out audit_confirm.json [--workers 8] [--timeout 10] [--limit N]
    python3 audit_final.py --manifest manifest_v2.json      --out audit_pilot.json
"""
import argparse, json, os, subprocess, sys, tempfile, collections, resource
from concurrent.futures import ThreadPoolExecutor

GROUPS = {"real": (1, 3, 5, 7), "generator": (2, 4, 6, 8)}


def norm(s):
    return "\n".join(l.rstrip() for l in (s or "").splitlines()).rstrip()


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (16 << 30, 16 << 30))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))


def run(code, stdin, timeout):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "prog.py")
        open(p, "w", encoding="utf8").write(code)
        try:
            r = subprocess.run([sys.executable, p], input=stdin, capture_output=True, text=True, timeout=timeout,
                               cwd=d, env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}, preexec_fn=limits)
            return {"rc": r.returncode, "out": norm(r.stdout), "err": r.stderr[-200:] if r.returncode else ""}
        except subprocess.TimeoutExpired:
            return {"rc": "timeout", "out": "", "err": ""}
        except Exception as e:  # noqa
            return {"rc": "error", "out": "", "err": str(e)[:200]}


def audit_sample(s, timeout):
    res = {}
    for c in s["conditions"]:
        cid = c["condition_id"]
        if c.get("status") != "ok":
            res[cid] = {"status": c.get("status"), "runs": []}
            continue
        cases = c.get("stdin_cases") or s.get("stdin_cases") or [""]
        res[cid] = {"status": "ok", "runs": [run(c["source_code"], x, timeout) for x in cases]}
    return s["sample_index"], res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8); ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    samples = json.load(open(a.manifest))["samples"]
    if a.limit: samples = samples[:a.limit]
    with ThreadPoolExecutor(a.workers) as ex:
        results = dict(ex.map(lambda s: audit_sample(s, a.timeout), samples))

    cond = collections.defaultdict(lambda: collections.Counter())
    bad, grp = [], collections.defaultdict(lambda: collections.Counter())
    for s in samples:
        idx = s["sample_index"]; r = results[idx]
        for cid, v in r.items():
            cond[cid]["cells"] += 1
            if v["status"] != "ok": cond[cid]["not_ok_in_manifest"] += 1; continue
            for run_ in v["runs"]:
                if run_["rc"] == "timeout": cond[cid]["timeout"] += 1
                elif run_["rc"] != 0: cond[cid]["nonzero_exit"] += 1
        for g, cids in GROUPS.items():
            present = [c for c in cids if c in r and r[c]["status"] == "ok"]
            grp[g]["samples"] += 1
            if len(present) < len(cids): grp[g]["missing_condition"] += 1
            n_cases = min((len(r[c]["runs"]) for c in present), default=0)
            ok = True
            for k in range(n_cases):
                outs = {c: (r[c]["runs"][k]["rc"], r[c]["runs"][k]["out"]) for c in present}
                if len(set(outs.values())) > 1:
                    ok = False
                    bad.append({"sample_index": idx, "group": g, "case": k, "outputs": {str(c): {"rc": o[0], "out": o[1][:200]} for c, o in outs.items()}})
                    break
            grp[g]["agree" if ok else "disagree"] += 1
    rep = {"manifest": a.manifest, "samples_audited": len(samples),
           "per_condition": {str(c): dict(v) for c, v in sorted(cond.items())},
           "per_group": {g: dict(v) for g, v in grp.items()}, "disagreements": bad}
    json.dump(rep, open(a.out, "w"), indent=1)
    print(f"manifest {a.manifest}: {len(samples)} samples")
    for c, v in sorted(cond.items()): print(f"  condition {c}: cells {v['cells']}, non-zero exit {v['nonzero_exit']}, timeouts {v['timeout']}, not ok in manifest {v['not_ok_in_manifest']}")
    for g, v in grp.items(): print(f"  {g} group: agree {v['agree']} / {v['samples']}, disagree {v['disagree']}, missing a condition {v['missing_condition']}")
    print(f"  disagreeing samples written to {a.out} ({len(bad)})")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
