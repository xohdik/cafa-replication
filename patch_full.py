import hashlib
DEMO4 = 'import json, glob\ndef fl(t):\n    p = t.strip().splitlines()\n    return p[0].strip() if p else \'\'\nprint(\'file | condition | n | accuracy | demo | first line == demo output | first line == "10" | correct first line == demo output\')\nfor f in sorted(glob.glob(\'rerun_*.jsonl\')):\n    R = [json.loads(l) for l in open(f) if l.strip()]\n    R = [r for r in R if r.get(\'status\') == \'ok\']\n    for c in sorted({r[\'condition_id\'] for r in R}):\n        A = [r for r in R if r[\'condition_id\'] == c]\n        d = A[0].get(\'demo\', \'orig\'); o = A[0].get(\'demo_out\', \'10\') if \'demo_out\' in A[0] else \'10\'\n        pd = (\'%.1f%%\' % (100.0 * sum(fl(r[\'prediction\']) == o for r in A) / len(A))) if o else \'-\'\n        ed = (\'%.1f%%\' % (100.0 * sum(fl(r[\'expected\']) == o for r in A) / len(A))) if o else \'-\'\n        p10 = 100.0 * sum(fl(r[\'prediction\']) == \'10\' for r in A) / len(A)\n        print(\'%-26s C%d n=%d acc=%.3f demo=%-7s copy %-6s | "10": %.1f%% | right answer is that string: %s\' % (f, c, len(A), sum(r[\'correct\'] for r in A) / len(A), d, pd, p10, ed))\n'
s = open('cafa_revision.py').read()
assert 'DEMOS' not in s, 'already patched'
old = '''    conds = {int(c) for c in a.conditions.split(",")}
    man = json.load(open(a.manifest))
    done ='''
new = '''    conds = {int(c) for c in a.conditions.split(",")}
    DEMOS = {"plus7": ("a = int(input())\\nprint(a + 7)\\n# Input:\\n4\\n# Output:\\n11", "11"),
             "reverse": ("s = input()\\nprint(s[::-1])\\n# Input:\\nabc\\n# Output:\\ncba", "cba"),
             "none": (None, None), "orig": (None, "10")}
    ORIG_DEMO = "# Program:\\nn = int(input())\\nprint(n * 2)\\n# Input:\\n5\\n# Output:\\n10\\n\\n"
    tmpl = PROMPT_TEMPLATE
    if a.demo != "orig":
        assert ORIG_DEMO in tmpl, "original demonstration not found in PROMPT_TEMPLATE"
        tmpl = tmpl.replace(ORIG_DEMO, "" if a.demo == "none" else "# Program:\\n" + DEMOS[a.demo][0] + "\\n\\n")
    man = json.load(open(a.manifest))
    done ='''
assert old in s; s = s.replace(old, new)
old = 'prompt = PROMPT_TEMPLATE.format(code=b["source_code"].strip(), stdin=stdin.strip())'
assert old in s; s = s.replace(old, 'prompt = tmpl.format(code=b["source_code"].strip(), stdin=stdin.strip())')
old = '"gguf": os.path.basename(a.gguf), "n_ctx": a.n_ctx}'
assert old in s; s = s.replace(old, '"gguf": os.path.basename(a.gguf), "n_ctx": a.n_ctx, "demo": a.demo, "demo_out": DEMOS[a.demo][1]}')
old = '    p.add_argument("--limit", type=int, default=0, help="only the first N programs (smoke test)")'
assert old in s; s = s.replace(old, old + '\n    p.add_argument("--demo", default="orig", choices=["orig", "plus7", "reverse", "none"], help="prompt demonstration: orig (the paper\'s), plus7, reverse, or none (zero-shot)")')
open('cafa_revision.py', 'w').write(s)
D = open('demo4.py', 'w')
D.write(DEMO4)
D.close()
print('patched; sha', hashlib.sha256(s.encode()).hexdigest()[:12])
