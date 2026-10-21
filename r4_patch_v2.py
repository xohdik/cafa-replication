s = open("r4_build_inputs.py").read()
a = s.index("def redraw(rng, t):"); b = s.index("def references(")
new = '''def is_bits(t):
    return len(t) >= 2 and set(t) <= {"0", "1"}


def mutate(txt, rng, att):
    """Six modes by attempt: integer values redrawn within the min-max range of the input (full / 30% of tokens), same-digit-length redraw (full / 30%),
    tokens shuffled within each non-header line, non-header lines shuffled. Strings and grids are redrawn over the alphabet that occurs in the input;
    the header line of multi-line inputs (counts) is kept."""
    mode = att % 6
    lines = txt.split("\\n")
    header = len(lines) > 2 and all(INT.match(t) for t in lines[0].split(" ") if t != "")
    body = list(range(1 if header else 0, len(lines)))
    toks = [lines[i].split(" ") for i in range(len(lines))]
    ints = [int(t) for i in body for t in toks[i] if t and INT.match(t) and not is_bits(t)]
    lo, hi = (min(ints), max(ints)) if ints else (0, 0)
    alpha = sorted({c for i in body for t in toks[i] if t and not INT.match(t) and not FLT.match(t) for c in t})
    if mode == 4:
        for i in body:
            idx = [k for k, t in enumerate(toks[i]) if t != ""]
            vals = [toks[i][k] for k in idx]; rng.shuffle(vals)
            for k, v in zip(idx, vals): toks[i][k] = v
        return "\\n".join(" ".join(t) for t in toks)
    if mode == 5:
        nz = [i for i in body if lines[i] != ""]; order = nz[:]; rng.shuffle(order)
        new = list(lines)
        for i, j in zip(nz, order): new[i] = lines[j]
        return "\\n".join(new)
    p = 1.0 if mode in (0, 2) else 0.3
    use_range = mode in (0, 1) and hi > lo
    for i in body:
        for k, t in enumerate(toks[i]):
            if t == "" or rng.random() > p: continue
            if is_bits(t):
                toks[i][k] = "".join(rng.choice("01") for _ in t)
            elif INT.match(t):
                a_ = abs(int(t)); sign = "-" if t.startswith("-") else ""
                if use_range: toks[i][k] = str(rng.randint(lo, hi))
                elif a_ == 0: pass
                else:
                    d = len(str(a_)); l2, h2 = (1, 9) if d == 1 else (10 ** (d - 1), 10 ** d - 1)
                    toks[i][k] = sign + str(rng.randint(l2, h2))
            elif FLT.match(t):
                dec = len(t.split(".")[1]); toks[i][k] = f"{float(t) * rng.uniform(0.7, 1.3):.{dec}f}"
            elif 2 <= len(alpha) <= 6:
                toks[i][k] = "".join(rng.choice(alpha) for _ in t)
            else:
                out = []
                for ch in t:
                    if ch.islower(): out.append(rng.choice("abcdefghijklmnopqrstuvwxyz"))
                    elif ch.isupper(): out.append(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
                    elif ch.isdigit(): out.append(rng.choice("0123456789"))
                    else: out.append(ch)
                toks[i][k] = "".join(out)
    return "\\n".join(" ".join(t) for t in toks)


'''
s = s[:a] + new + s[b:]
assert s.count("cand = mutate(I0, rng, 1.0 if att % 2 == 0 else 0.3)") == 1
s = s.replace("cand = mutate(I0, rng, 1.0 if att % 2 == 0 else 0.3)", "cand = mutate(I0, rng, att)")
assert s.count("MAX_REFS, MAX_ATT, WANT = 6, 40, 2") == 1
s = s.replace("MAX_REFS, MAX_ATT, WANT = 6, 40, 2", "MAX_REFS, MAX_ATT, WANT = 6, 60, 2")
assert s.count("if not diverse and att < 30: continue") == 1
s = s.replace("if not diverse and att < 30: continue", "if not diverse and att < 45: continue")
open("r4_build_inputs.py", "w").write(s)
print("patched")
