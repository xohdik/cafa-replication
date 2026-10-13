import json, sys, time, numpy as np
sys.path.insert(0, ".")
from cafa_revision import stdin_of
from scoring_harness import PROMPT_TEMPLATE
from llama_cpp import Llama
gguf, demo, out = sys.argv[1], sys.argv[2], sys.argv[3]
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 0
ORIG = "# Program:\nn = int(input())\nprint(n * 2)\n# Input:\n5\n# Output:\n10\n\n"
assert ORIG in PROMPT_TEMPLATE
tmpl = PROMPT_TEMPLATE if demo == "orig" else PROMPT_TEMPLATE.replace(ORIG, "")
man = json.load(open("manifest_confirm.json"))
llm = Llama(model_path=gguf, n_gpu_layers=-1, n_ctx=8192, logits_all=True, verbose=False)
C = llm.tokenize(b"10", add_bos=False)
print("tokens of '10':", C, flush=True)
def lsm(x):
    x = x.astype(np.float64); x = x - x.max()
    return x - np.log(np.exp(x).sum())
rec = {1: [], 2: [], 6: []}
t0 = time.time(); n = 0
with open(out, "w") as fo:
    for s in man["samples"][: limit or None]:
        for b in s["conditions"]:
            cid = b["condition_id"]; stdin = stdin_of(s, b)
            if cid not in rec or b.get("status") != "ok" or not b.get("source_code") or not stdin:
                continue
            pt = llm.tokenize(tmpl.format(code=b["source_code"].strip(), stdin=stdin.strip()).encode("utf-8"), add_bos=True)
            if len(pt) + len(C) > 8000:
                continue
            llm.reset(); llm.eval(pt + C)
            sc = llm.scores; m = len(pt)
            lp = 0.0
            for j, t in enumerate(C):
                lp += lsm(sc[m - 1 + j])[t]
            top1 = int(np.argmax(sc[m - 1])) == C[0]
            r = {"sample_index": s["sample_index"], "condition_id": cid, "p10": float(np.exp(lp)), "top1_first_token": top1}
            rec[cid].append(r); fo.write(json.dumps(r) + "\n"); n += 1
            if n % 200 == 0:
                print(f"  ...{n} prompts ({time.time()-t0:.0f}s)", flush=True)
print(f"== {gguf} demo={demo}")
for c in (1, 2, 6):
    v = np.array([r["p10"] for r in rec[c]]); t = np.mean([r["top1_first_token"] for r in rec[c]])
    print(f"C{c}: n={len(v)} median P('10')={np.median(v):.4f} mean={v.mean():.4f} share top-1 first token = '10' start: {t*100:.1f}%")
print("done", flush=True)
