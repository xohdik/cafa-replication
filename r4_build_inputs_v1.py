#!/usr/bin/env python3
"""r4_build_inputs.py -- Revision 4 (multi-input oracle), CPU only.
For every real program of the confirmation manifest:
  1. take the official CodeNet input (stdin_cases[0]) and the other Python submissions of the same problem; keep those that reproduce the official
     output on the official input (reference solutions, at most MAX_REFS);
  2. build up to two further inputs by redrawing the values of the official input (same line and token layout, same digit length; the header line
     of multi-line inputs is kept); an input is accepted only if the real program runs on it and at least one reference solution agrees with it
     (tier A: >= 2 agree and at least half of the running references; tier B: exactly one agrees and at least half agree);
  3. run conditions 1, 3, 5, 7 on all available inputs and compare with condition 1 (real programs: shuffle, obfuscation, both);
     run conditions 2, 4, 6, 8 (G1) on their three stdin cases and compare among themselves.
Writes r4_inputs.json (inputs, expected outputs, equivalence results) and r4_report.md. Deterministic (seed from the sample index)."""
import argparse, collections, hashlib, json, os, random, re, sys
import multiprocessing as mp
from g2_features import run_code

MAX_REFS, MAX_ATT, WANT = 6, 40, 2
INT = re.compile(r"^[+-]?\d+$"); FLT = re.compile(r"^[+-]?\d*\.\d+$")
TIMEOUT, MEM = 10.0, 4096


def sn(o):
    return "\n".join(l.rstrip() for l in o.strip().splitlines())


def seed_of(*a):
    return int(hashlib.sha256("|".join(map(str, a)).encode()).hexdigest()[:8], 16)


def redraw(rng, t):
    if INT.match(t):
        a = abs(int(t)); sign = "-" if t.startswith("-") else ""
        if a == 0: return t
        d = len(str(a)); lo, hi = (1, 9) if d == 1 else (10 ** (d - 1), 10 ** d - 1)
        return sign + str(rng.randint(lo, hi))
    if FLT.match(t):
        dec = len(t.split(".")[1]); v = float(t) * rng.uniform(0.7, 1.3)
        return f"{v:.{dec}f}"
    out = []
    for ch in t:
        if ch.islower(): out.append(rng.choice("abcdefghijklmnopqrstuvwxyz"))
        elif ch.isupper(): out.append(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        elif ch.isdigit(): out.append(rng.choice("0123456789"))
        else: out.append(ch)
    return "".join(out)


def mutate(txt, rng, p):
    lines = txt.split("\n"); res = []
    for li, line in enumerate(lines):
        toks = line.split(" ")
        keep = li == 0 and len(lines) > 2 and all(INT.match(t) for t in toks if t != "")
        res.append(" ".join(t if (t == "" or keep or rng.random() > p) else redraw(rng, t) for t in toks))
    return "\n".join(res)


def references(cn, pid, real_src):
    d = os.path.join(cn, "data", pid, "Python")
    ip = os.path.join(cn, "derived", "input_output", "data", pid)
    try:
        exp = open(os.path.join(ip, "output.txt"), errors="replace").read(); official_in = open(os.path.join(ip, "input.txt"), errors="replace").read()
    except OSError:
        return None, None, []
    files = sorted(os.listdir(d))[:60] if os.path.isdir(d) else []
    refs = []
    for f in files:
        try: src = open(os.path.join(d, f), errors="replace").read()
        except OSError: continue
        if src.strip() == real_src.strip(): continue
        o, e = run_code(src, official_in, timeout=TIMEOUT, mem_mb=MEM)
        if e is None and sn(o) == sn(exp):
            refs.append(src)
            if len(refs) >= MAX_REFS: break
    return official_in, exp, refs


def valid(P, refs, cand):
    o, e = run_code(P, cand, timeout=TIMEOUT, mem_mb=MEM)
    if e or not o.strip(): return None
    ran = agree = 0
    for r in refs:
        ro, re_ = run_code(r, cand, timeout=TIMEOUT, mem_mb=MEM)
        if re_ is None:
            ran += 1; agree += sn(ro) == sn(o)
    if agree >= 2 and agree * 2 >= ran: tier = "A"
    elif agree == 1 and agree * 2 >= ran: tier = "B"
    else: return None
    return o, tier, agree, ran


def work(args):
    rec, cn = args
    conds = {c["condition_id"]: c for c in rec["conditions"]}
    P = conds[1]["source_code"]; I0 = conds[1]["stdin_cases"][0]
    out = {"sample_index": rec["sample_index"], "problem_id": rec["problem_id"]}
    official_in, exp, refs = references(cn, rec["problem_id"], P)
    out["official_input_found"] = official_in is not None; out["official_equals_stdin0"] = (official_in == I0) if official_in is not None else None
    out["n_refs"] = len(refs)
    o0, e0 = run_code(P, I0, timeout=TIMEOUT, mem_mb=MEM)
    out["real_runs_on_official"] = e0 is None
    out["real_matches_official_output"] = (e0 is None and exp is not None and sn(o0) == sn(exp))
    extra, seen, outs_seen = [], {I0}, {sn(o0)} if e0 is None else set()
    rng = random.Random(seed_of("r4", rec["sample_index"]))
    if refs and e0 is None:
        for att in range(MAX_ATT):
            if len(extra) >= WANT: break
            cand = mutate(I0, rng, 1.0 if att % 2 == 0 else 0.3)
            if cand in seen: continue
            seen.add(cand)
            v = valid(P, refs, cand)
            if v is None: continue
            o, tier, agree, ran = v; diverse = sn(o) not in outs_seen
            if not diverse and att < 30: continue
            outs_seen.add(sn(o)); extra.append({"stdin": cand, "expected": o, "tier": tier, "agree": agree, "ran": ran, "diverse": diverse})
    out["extra"] = extra
    inputs = [I0] + [x["stdin"] for x in extra]
    base = {}
    for k, s in enumerate(inputs):
        base[k] = (o0, e0) if k == 0 else run_code(P, s, timeout=TIMEOUT, mem_mb=MEM)
    eq = {}
    for cid in (3, 5, 7):
        src = conds[cid]["source_code"]; changed = src.strip() != P.strip(); res = []
        for k, s in enumerate(inputs):
            o, e = (base[k] if not changed else run_code(src, s, timeout=TIMEOUT, mem_mb=MEM))
            res.append("err" if e else ("ok" if (base[k][1] is None and sn(o) == sn(base[k][0])) else "diff"))
        eq[str(cid)] = {"changed": changed, "per_input": res}
    out["real_equiv"] = eq
    g1 = []
    for ci, s in enumerate(conds[2]["stdin_cases"]):
        outs, errs = {}, 0
        for cid in (2, 4, 6, 8):
            o, e = run_code(conds[cid]["source_code"], s, timeout=TIMEOUT, mem_mb=MEM)
            if e: errs += 1
            else: outs[cid] = sn(o)
        g1.append({"err": errs, "distinct": len(set(outs.values()))})
    out["g1"] = g1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest_confirm.json"); ap.add_argument("--cn", default="/data/workzone/PhD/Project_CodeNet")
    ap.add_argument("--out", default="r4_inputs.json"); ap.add_argument("--jobs", type=int, default=40); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    m = json.load(open(a.manifest)); samples = m["samples"] if isinstance(m, dict) else m
    if a.limit: samples = samples[:a.limit]
    with mp.Pool(a.jobs) as pool:
        res = list(pool.imap(work, [(s, a.cn) for s in samples], chunksize=2))
    json.dump({"manifest": a.manifest, "manifest_sha256": hashlib.sha256(open(a.manifest, "rb").read()).hexdigest(), "seed_rule": "sha256('r4|index')[:8]",
               "max_refs": MAX_REFS, "max_attempts": MAX_ATT, "want_extra": WANT, "records": res}, open(a.out, "w"))
    n = len(res); md = [f"# Revision 4: multi-input oracle ({n} real programs; real = conditions 1, 3, 5, 7; G1 = conditions 2, 4, 6, 8)\n"]
    md.append(f"- official CodeNet input found: {sum(r['official_input_found'] for r in res)}; equals stdin_cases[0]: {sum(bool(r['official_equals_stdin0']) for r in res)}")
    md.append(f"- real program runs on the official input: {sum(r['real_runs_on_official'] for r in res)}; reproduces the official output: {sum(r['real_matches_official_output'] for r in res)}")
    nr = collections.Counter(min(r["n_refs"], 3) for r in res); md.append(f"- reference solutions per problem (0 / 1 / 2 / 3 or more): {nr[0]} / {nr[1]} / {nr[2]} / {nr[3]}")
    ne = collections.Counter(len(r["extra"]) for r in res); md.append(f"- extra valid inputs per program (0 / 1 / 2): {ne[0]} / {ne[1]} / {ne[2]}")
    tiers = collections.Counter(x["tier"] for r in res for x in r["extra"]); md.append(f"- accepted inputs by tier: A {tiers['A']}, B {tiers['B']}; with output different from the official output: {sum(x['diverse'] for r in res for x in r['extra'])} of {sum(tiers.values())}")
    md += ["\n## Real conditions against condition 1 (programs with the condition's code changed from condition 1; 'first only' = passes the official input but differs or fails on an extra input)\n",
           "| condition | changed | equal on every available input | equal on first input only | differs or errors on the official input | programs with >= 1 extra input |", "|---|---|---|---|---|---|"]
    names = {3: "3 (shuffle)", 5: "5 (obfuscation)", 7: "7 (both)"}
    for cid in (3, 5, 7):
        ch = [r for r in res if r["real_equiv"][str(cid)]["changed"]]
        allok = sum(all(x == "ok" for x in r["real_equiv"][str(cid)]["per_input"]) for r in ch)
        first = sum(r["real_equiv"][str(cid)]["per_input"][0] == "ok" and any(x != "ok" for x in r["real_equiv"][str(cid)]["per_input"][1:]) for r in ch)
        bad0 = sum(r["real_equiv"][str(cid)]["per_input"][0] != "ok" for r in ch)
        withx = sum(len(r["extra"]) >= 1 for r in ch)
        md.append(f"| {names[cid]} | {len(ch)} | {allok} | {first} | {bad0} | {withx} |")
    bad = [r for r in res if any(x != "ok" for c in ("3", "5", "7") for x in r["real_equiv"][c]["per_input"][1:])]
    md.append(f"\n- programs where at least one real condition fails on an extra input: {len(bad)}")
    md += ["\n## G1 conditions (2, 4, 6, 8) on their three stdin cases\n", f"- samples with a run error in any G1 condition: {sum(any(g['err'] for g in r['g1']) for r in res)}; with differing outputs between conditions on some case: {sum(any(g['distinct'] > 1 for g in r['g1']) for r in res)}"]
    open("r4_report.md", "w").write("\n".join(md)); print("\n".join(md))


if __name__ == "__main__":
    main()
