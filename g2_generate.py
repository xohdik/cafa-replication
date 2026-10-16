#!/usr/bin/env python3
"""
g2_generate.py -- generator G2 for CAFA: a second, independently constructed source of generator-produced programs.

G2 shares NO code, templates, constants, input or padding convention with G1. It reads only the REAL program of each sample
(never G1's program) and builds, for that sample, a program that is matched on measured properties of the real one:
non-blank lines, cyclomatic complexity, nesting depth, output shape (0 / 1 / several lines), number of stdin lines and tokens,
digit length of input integers, and identifier style (mean name length, share of one-letter names).
It deliberately differs from G1 in what G1 held fixed or faked:
  * input    : a fresh random stdin per sample (shape and magnitude from the real input; values never copied), plus two more cases;
  * output   : computed from the input by live code; values range freely (not small constants);
  * padding  : none. Every assigned name is read later (AST def-use check); length is reached with computation, not dead stores;
  * templates: a different statement grammar (readers, accumulators, filters, pair loops, string ops, helper functions, ...);
  * naming   : drawn from three vocabularies (terse / mixed / descriptive) chosen to match the real program's identifier statistics.
Usage (cafa env, from capa/):
    python3 g2_generate.py --manifest manifest_confirm.json --out g2_base.json [--seed 20261014] [--limit N]
Writes g2_base.json (one record per sample) and g2_report.json. Deterministic given the seed. Run `--selftest` to check the
declared (lines, cc, depth) of every statement form against measurement.
"""
import argparse
import ast
import collections
import hashlib
import json
import random
import sys

from g2_features import code_features, stdin_features, stdout_features, run_code, norm, user_names, REAL_LIMITS

MASTER_SEED = 20261014

BANK = {
    "terse": {"scalar": list("nmkabcxypqtrzNMKHWL"), "list": ["a", "l", "v", "xs", "b", "c", "d", "A", "B", "S", "P"], "str": list("stwuSTW"),
              "strs": ["ws", "ss", "l", "p", "S", "W"], "acc": list("rstxyzcdRSTX"), "loop": list("ijkvexywIJ"), "func": list("fghpq")},
    "mixed": {"scalar": ["n", "m", "num", "val", "cnt", "size", "lim", "x", "y", "k"],
              "list": ["arr", "nums", "lst", "data", "vals", "a", "seq"], "str": ["s", "text", "st", "word", "line"],
              "strs": ["words", "parts", "toks", "items"],
              "acc": ["ans", "res", "tot", "mx", "mn", "cnt", "total", "best", "out", "acc"],
              "loop": ["i", "j", "v", "x", "e", "item", "k"], "func": ["f", "calc", "go", "solve", "step"]},
    "long": {"scalar": ["count", "limit", "target", "width", "length", "offset", "base", "step_size", "upper_bound"],
             "list": ["numbers", "values", "elements", "sequence", "items", "readings", "scores", "data_list"],
             "str": ["text", "sentence", "word", "message", "line_text"], "strs": ["tokens", "word_list", "pieces", "names"],
             "acc": ["total_sum", "max_value", "result", "running_total", "match_count", "min_value", "answer", "best_so_far", "accumulated"],
             "loop": ["index", "value", "element", "item", "number", "current", "ch", "pos"],
             "func": ["compute", "transform", "process_value", "helper", "score_of"]},
}


ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

class Var:
    def __init__(self, name, kind, derived, n=None):
        self.name, self.kind, self.derived, self.used, self.n = name, kind, derived, False, n


class Prog:
    """Builds one program: a list of source lines plus a pool of typed variables."""
    def __init__(self, rng, mix, p_indep):
        self.rng, self.mix, self.p_indep = rng, mix, p_indep
        self.lines, self.pool, self.taken, self.imports = [], [], set(), set()

    # --- naming
    def name(self, role):
        for _ in range(50):
            style = self.rng.choices(["terse", "mixed", "long"], weights=[self.mix["terse"], self.mix["mixed"], self.mix["long"]])[0]
            cand = self.rng.choice(BANK[style][role])
            if cand in self.taken and style == "terse":
                free = [c for c in ALPHA if c not in self.taken]
                if free: cand = self.rng.choice(free)
            if cand not in self.taken:
                self.taken.add(cand); return cand
        base = self.rng.choice(BANK["mixed"][role]); k = 2
        while f"{base}{k}" in self.taken: k += 1
        self.taken.add(f"{base}{k}"); return f"{base}{k}"

    def loopvar(self):
        for _ in range(50):
            style = self.rng.choices(["terse", "mixed", "long"], weights=[self.mix["terse"], self.mix["mixed"], self.mix["long"]])[0]
            cand = self.rng.choice(BANK[style]["loop"])
            if cand in self.taken and style == "terse":
                free = [c for c in "ijkvexywabcdfghmnpqrstuz" if c not in self.taken]
                if free: cand = self.rng.choice(free)
            if cand not in self.taken:
                return cand
        return "q_"

    # --- operands
    def add(self, role, kind, derived=True, n=None):
        v = Var(self.name(role), kind, derived, n); self.pool.append(v); return v

    def pick(self, kind, minn=0):
        c = [v for v in self.pool if v.kind == kind and (v.n is None or v.n >= minn)]
        if not c: return None
        ind = [v for v in c if not v.derived]
        if ind and self.rng.random() < self.p_indep:
            c = ind
        un = [v for v in c if not v.used]
        if un and self.rng.random() < 0.7:
            c = un
        v = self.rng.choice(c); v.used = True; return v

    def pick_target(self):
        c = [v for v in self.pool if v.kind == "int" and v.derived]
        return self.rng.choice(c) if c else None

    def emit(self, *ls):
        self.lines.extend(ls)

    def src(self):
        head = sorted(self.imports)
        return "\n".join(head + self.lines)


def lit(rng, lo=2, hi=9): return rng.randint(lo, hi)


# ---------------------------------------------------------------- statement forms: (key, kind needed, lines, cc, depth)
# each fn(P, a, b) emits lines and registers its result variable(s); a/b are operand Vars.
FORMS = []


def form(need, lines, cc, depth, weight=1.0):
    def deco(fn):
        FORMS.append((fn.__name__, need, lines, cc, depth, weight, fn)); return fn
    return deco


# --- over a list of ints
@form(("ints",), 1, 0, 0, 1.0)
def sum_builtin(P, a, b): t = P.add("acc", "int"); P.emit(f"{t.name} = sum({a.name})")
@form(("ints",), 3, 1, 1, 1.0)
def sum_loop(P, a, b):
    t = P.add("acc", "int"); v = P.loopvar(); P.emit(f"{t.name} = 0", f"for {v} in {a.name}:", f"    {t.name} += {v}")
@form(("ints",), 4, 2, 2, 1.2)
def sum_filter(P, a, b):
    t = P.add("acc", "int"); v = P.loopvar(); m = lit(P.rng, 2, 9)
    P.emit(f"{t.name} = 0", f"for {v} in {a.name}:", f"    if {v} % {m} == {P.rng.randint(0, m - 1)}:", f"        {t.name} += {v}")
@form(("ints",), 1, 0, 0, 0.7)
def max_builtin(P, a, b):
    t = P.add("acc", "int"); f = P.rng.choice(["max", "min"]); P.emit(f"{t.name} = {f}({a.name})")
@form(("ints",), 4, 2, 2, 1.0)
def max_loop(P, a, b):
    t = P.add("acc", "int"); v = P.loopvar()
    op = P.rng.choice([">", "<"])
    P.emit(f"{t.name} = {a.name}[0]", f"for {v} in {a.name}:", f"    if {v} {op} {t.name}:", f"        {t.name} = {v}")
@form(("ints",), 4, 2, 2, 1.2)
def count_cond(P, a, b):
    t = P.add("acc", "int"); v = P.loopvar(); c = P.rng.randint(0, 50)
    P.emit(f"{t.name} = 0", f"for {v} in {a.name}:", f"    if {v} > {c}:", f"        {t.name} += 1")
@form(("ints",), 5, 1, 1, 0.9)
def prefix(P, a, b):
    t = P.add("list", "ints"); r = P.add("acc", "int"); v = P.loopvar(); r.used = True
    P.emit(f"{t.name} = []", f"{r.name} = 0", f"for {v} in {a.name}:", f"    {r.name} += {v}", f"    {t.name}.append({r.name})")
@form(("ints",), 1, 2, 0, 1.0)
def filter_comp(P, a, b):
    t = P.add("list", "ints"); v = P.loopvar(); P.emit(f"{t.name} = [{v} for {v} in {a.name} if {v} % 2 == {P.rng.randint(0, 1)}]")
@form(("ints",), 1, 1, 0, 1.0)
def map_comp(P, a, b):
    t = P.add("list", "ints"); v = P.loopvar(); P.emit(f"{t.name} = [{v} * {lit(P.rng, 2, 7)} % {P.rng.choice([11, 97, 101, 1000])} for {v} in {a.name}]")
@form(("ints",), 1, 0, 0, 0.6)
def sort_list(P, a, b):
    t = P.add("list", "ints"); P.emit(f"{t.name} = sorted({a.name}{', reverse=True' if P.rng.random() < 0.3 else ''})")
@form(("ints",), 5, 3, 3, 0.9)
def pairs(P, a, b):
    t = P.add("acc", "int"); i, j = "i", "j"
    if i in P.taken or j in P.taken: i, j = "p_", "q_"
    c = P.rng.randint(0, 80)
    P.emit(f"{t.name} = 0", f"for {i} in range(len({a.name})):", f"    for {j} in range({i} + 1, len({a.name})):",
           f"        if {a.name}[{i}] + {a.name}[{j}] > {c}:", f"            {t.name} += 1")
@form(("ints",), 3, 1, 1, 0.9)
def enum_sum(P, a, b):
    t = P.add("acc", "int"); i, v = "i", P.loopvar()
    if i in P.taken or i == v: i = "idx_"
    P.emit(f"{t.name} = 0", f"for {i}, {v} in enumerate({a.name}):", f"    {t.name} += {i} * {v}")
@form(("ints",), 4, 1, 1, 0.8)
def freq(P, a, b):
    d = P.add("acc", "int"); v = P.loopvar(); f = P.name("acc"); P.pool.append(Var(f, "dict", True)); P.pool[-1].used = True
    P.emit(f"{f} = {{}}", f"for {v} in {a.name}:", f"    {f}[{v}] = {f}.get({v}, 0) + 1", f"{d.name} = max({f}.values())")
@form(("ints",), 1, 2, 0, 0.9)
def count_gen(P, a, b):
    t = P.add("acc", "int"); v = P.loopvar(); P.emit(f"{t.name} = sum(1 for {v} in {a.name} if {v} > {P.rng.randint(0, 30)})")
@form(("ints",), 1, 0, 0, 0.8)
def alt_sum(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = sum({a.name}[::2]) - sum({a.name}[1::2])")
@form(("ints",), 1, 0, 0, 0.8)
def len_ops(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = len({a.name}) * {lit(P.rng, 2, 9)} + {P.rng.randint(0, 20)}")

@form(("ints",), 6, 4, 4, 0.8)
def nested_count(P, a, b):
    t = P.add("acc", "int"); i, j = "i", "j"
    if i in P.taken or j in P.taken: i, j = "p_", "q_"
    P.emit(f"{t.name} = 0", f"for {i} in range(len({a.name})):", f"    for {j} in range(len({a.name})):",
           f"        if {i} != {j}:", f"            if {a.name}[{i}] > {a.name}[{j}]:", f"                {t.name} += 1")
@form(("int", "int"), 4, 2, 1, 1.0)
def and_cond(P, a, b):
    t = P.add("acc", "int"); op = P.rng.choice(["and", "or"])
    P.emit(f"if {a.name} > {P.rng.randint(0, 30)} {op} {b.name} < {P.rng.randint(5, 60)}:", f"    {t.name} = {a.name} + {b.name}", "else:", f"    {t.name} = {a.name} - {b.name}")
@form(("ints",), 7, 2, 2, 0.9)
def split_sum(P, a, b):
    t = P.add("acc", "int"); u = P.add("acc", "int"); v = P.loopvar(); u.used = True
    P.emit(f"{t.name} = 0", f"{u.name} = 0", f"for {v} in {a.name}:", f"    if {v} % 2:", f"        {t.name} += {v}")
    P.emit(f"    else:", f"        {u.name} += {v}")
# --- over scalar ints
@form(("int", "int"), 1, 0, 0, 1.2)
def arith(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = ({a.name} * {lit(P.rng, 2, 9)} + {b.name}) % {P.rng.choice([97, 101, 1009, 10007])}")
@form(("int", "int"), 4, 1, 1, 1.0)
def cond_assign(P, a, b):
    t = P.add("acc", "int")
    P.emit(f"if {a.name} > {b.name}:", f"    {t.name} = {a.name} - {b.name}", "else:", f"    {t.name} = {b.name} - {a.name}")
@form(("int", "int"), 1, 1, 0, 1.0)
def ternary(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = {a.name} - {b.name} if {a.name} > {b.name} else {b.name} - {a.name}")
@form(("int", "int"), 3, 1, 1, 0.8)
def gcd(P, a, b):
    t = P.add("acc", "int"); y = P.name("scalar"); P.pool.append(Var(y, "int", True)); P.pool[-1].used = True
    P.emit(f"{t.name}, {y} = abs({a.name}), abs({b.name})", f"while {y}:", f"    {t.name}, {y} = {y}, {t.name} % {y}")
@form(("int",), 5, 1, 1, 0.8)
def halve(P, a, b):
    t = P.add("acc", "int"); u = P.name("scalar"); P.pool.append(Var(u, "int", True)); P.pool[-1].used = True
    P.emit(f"{t.name} = 0", f"{u} = abs({a.name})", f"while {u} > 1:", f"    {u} //= 2", f"    {t.name} += 1")
@form(("int",), 1, 1, 0, 0.8)
def digit_sum(P, a, b):
    t = P.add("acc", "int"); ch = P.loopvar(); P.emit(f"{t.name} = sum(int({ch}) for {ch} in str(abs({a.name})))")
@form(("int",), 3, 1, 1, 0.8)
def range_loop(P, a, b):
    t = P.add("acc", "int"); k = P.loopvar()
    P.emit(f"{t.name} = 0", f"for {k} in range({lit(P.rng, 3, 12)}):", f"    {t.name} += ({k} * {a.name}) % {P.rng.choice([7, 13, 29])}")
@form(("int",), 3, 1, 1, 0.6)
def fib(P, a, b):
    t = P.add("acc", "int"); q = P.name("scalar"); P.pool.append(Var(q, "int", True)); P.pool[-1].used = True
    P.emit(f"{t.name}, {q} = {a.name} % 5, 1", f"for _ in range({lit(P.rng, 5, 20)}):", f"    {t.name}, {q} = {q}, ({t.name} + {q}) % 1009")
@form(("int", "int"), 1, 0, 0, 0.8)
def span(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = max({a.name}, {b.name}) - min({a.name}, {b.name})")
@form(("int",), 6, 2, 2, 0.7)
def chain_if(P, a, b):
    t = P.add("acc", "int"); m1, m2 = P.rng.sample([2, 3, 5, 7], 2)
    P.emit(f"if {a.name} % {m1} == 0:", f"    {t.name} = {a.name} // {m1}", f"elif {a.name} % {m2} == 0:",
           f"    {t.name} = {a.name} * {m2}", "else:", f"    {t.name} = {a.name} + 1")
# --- over a string
@form(("str",), 1, 0, 0, 0.8)
def str_rev(P, a, b):
    t = P.add("str", "str"); P.emit(f"{t.name} = {a.name}[::-1]")
@form(("str",), 1, 0, 0, 0.8)
def str_case(P, a, b):
    t = P.add("str", "str"); P.emit(f"{t.name} = {a.name}.{P.rng.choice(['upper', 'lower', 'swapcase', 'title'])}()")
@form(("str",), 1, 0, 0, 0.8)
def str_count(P, a, b):
    t = P.add("acc", "int"); ch = P.rng.choice(["a", "e", "1", " ", "o"])
    P.emit(f'{t.name} = {a.name}.count("{ch}")')
@form(("str",), 1, 2, 0, 1.0)
def vowels(P, a, b):
    t = P.add("acc", "int"); ch = P.loopvar(); P.emit(f'{t.name} = sum(1 for {ch} in {a.name} if {ch} in "aeiou")')
@form(("str",), 4, 2, 2, 0.9)
def str_build(P, a, b):
    t = P.add("str", "str"); ch = P.loopvar()
    P.emit(f'{t.name} = ""', f"for {ch} in {a.name}:", f'    if {ch} != "{P.rng.choice("aeiost")}":', f"        {t.name} += {ch}")
@form(("str",), 1, 1, 0, 0.7)
def palin(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = 1 if {a.name} == {a.name}[::-1] else 0")
@form(("str",), 1, 1, 0, 0.8)
def ord_sum(P, a, b):
    t = P.add("acc", "int"); ch = P.loopvar(); P.emit(f"{t.name} = sum(ord({ch}) for {ch} in {a.name}) % {P.rng.choice([101, 997, 1000])}")
@form(("str",), 1, 0, 0, 0.6)
def str_len(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = len({a.name}) * {lit(P.rng, 2, 6)} + {P.rng.randint(0, 9)}")
# --- over a list of strings
@form(("strs",), 1, 1, 0, 1.0)
def words_len(P, a, b):
    t = P.add("acc", "int"); w = P.loopvar(); P.emit(f"{t.name} = sum(len({w}) for {w} in {a.name})")
@form(("strs",), 1, 0, 0, 0.8)
def words_join(P, a, b):
    t = P.add("str", "str"); P.emit(f'{t.name} = "{P.rng.choice(["-", " ", ",", ""])}".join(sorted({a.name}))')
@form(("strs",), 1, 1, 0, 0.8)
def words_rev(P, a, b):
    t = P.add("strs", "strs"); w = P.loopvar(); P.emit(f"{t.name} = [{w}[::-1] for {w} in {a.name}]")
@form(("strs",), 1, 0, 0, 0.7)
def words_longest(P, a, b):
    t = P.add("str", "str"); P.emit(f"{t.name} = max({a.name}, key=len)")
# --- updates of an existing accumulator (fewer new names, longer dependency chains, as in real code)
@form(("ints",), 1, 0, 0, 0.9)
def upd_add(P, a, b):
    t = P.pick_target(); P.emit(f"{t.name} += sum({a.name})"); t.used = False
@form(("int",), 1, 0, 0, 0.9)
def upd_mul(P, a, b):
    t = P.pick_target(); P.emit(f"{t.name} = {t.name} * {lit(P.rng, 2, 7)} % {P.rng.choice([97, 1009, 10007])} + {a.name}"); t.used = False
@form(("ints",), 2, 1, 1, 0.9)
def upd_loop(P, a, b):
    t = P.pick_target(); v = P.loopvar(); P.emit(f"for {v} in {a.name}:", f"    {t.name} += {v} * {lit(P.rng, 2, 5)}"); t.used = False
@form(("int",), 4, 1, 1, 0.8)
def upd_cond(P, a, b):
    t = P.pick_target(); P.emit(f"if {a.name} > {P.rng.randint(0, 20)}:", f"    {t.name} += {a.name}", "else:", f"    {t.name} -= 1"); t.used = False
# --- library calls (real programs import modules)
@form(("int", "int"), 1, 0, 0, 0.5)
def math_gcd(P, a, b):
    P.imports.add("import math"); t = P.add("acc", "int"); P.emit(f"{t.name} = math.gcd({a.name}, {b.name})")
@form(("int",), 1, 0, 0, 0.5)
def math_isqrt(P, a, b):
    P.imports.add("import math"); t = P.add("acc", "int"); P.emit(f"{t.name} = math.isqrt(abs({a.name}))")
@form(("int",), 1, 0, 0, 0.4)
def math_fact(P, a, b):
    P.imports.add("import math"); t = P.add("acc", "int"); P.emit(f"{t.name} = math.factorial(abs({a.name}) % 9)")
@form(("ints",), 1, 0, 0, 0.5)
def counter_max(P, a, b):
    P.imports.add("from collections import Counter"); t = P.add("acc", "int"); P.emit(f"{t.name} = max(Counter({a.name}).values())")
TARGET_FORMS = {"upd_add", "upd_mul", "upd_loop", "upd_cond"}
# --- helper function (defined, then applied)
@form((), 2, 0, 1, 0.7)
def def_func(P, a, b):
    f = P.name("func"); x = "x" if "x" not in P.taken else "z_"
    P.pool.append(Var(f, "func", True))
    P.emit(f"def {f}({x}):", f"    return {x} * {lit(P.rng, 2, 6)} % {P.rng.choice([11, 97, 101])} + {lit(P.rng, 1, 9)}")
@form(("func", "ints"), 1, 1, 0, 1.0)
def apply_func_list(P, a, b):
    t = P.add("list", "ints"); v = P.loopvar(); P.emit(f"{t.name} = [{a.name}({v}) for {v} in {b.name}]")
@form(("func", "int"), 1, 0, 0, 1.0)
def apply_func_scalar(P, a, b):
    t = P.add("acc", "int"); P.emit(f"{t.name} = {a.name}({b.name})")

FORM_BY_NAME = {f[0]: f for f in FORMS}
FORM_MINN = {"pairs": 3, "prefix": 2, "freq": 2, "sort_list": 2, "max_loop": 2, "alt_sum": 2, "enum_sum": 2, "words_join": 2, "words_longest": 2}


def kinds_available(P):
    return collections.Counter(v.kind for v in P.pool)


def applicable(P):
    have = kinds_available(P)
    out = []
    for name, need, lines, cc, depth, w, fn in FORMS:
        req = collections.Counter(need)
        if not all(have[k] >= n for k, n in req.items()):
            continue
        if name in TARGET_FORMS and not any(v.kind == "int" and v.derived for v in P.pool):
            continue
        mn = FORM_MINN.get(name, 0)
        if mn and not any(v.kind in ("ints", "strs") and v.kind in need and (v.n is None or v.n >= mn) for v in P.pool):
            continue
        out.append((name, need, lines, cc, depth, w, fn))
    return out


def apply_form(P, entry):
    name, need, lines, cc, depth, w, fn = entry
    ops = []
    mn = FORM_MINN.get(name, 0)
    for k in need:
        # distinct operands for repeated kinds
        for _ in range(8):
            v = P.pick(k, mn)
            if v is not None and v not in ops: break
        else:
            v = P.pick(k, mn)
        ops.append(v)
    a = ops[0] if ops else None; b = ops[1] if len(ops) > 1 else (ops[0] if ops else None)
    fn(P, a, b)




# ---------------------------------------------------------------- wrappers: put a form inside a loop or a length guard
def apply_wrapped(P, entry_list, depth_left):
    """Pick a small form, emit it, wrap its lines in a block (and possibly wrap again)."""
    rng = P.rng
    small = [e for e in entry_list if e[2] <= 4 and e[0] not in ("def_func",)]
    if not small: return False
    mark = len(P.lines)
    apply_form(P, rng.choices(small, weights=[e[5] for e in small])[0])
    inner = P.lines[mark:]; del P.lines[mark:]
    kind = rng.choice(["for", "guard"])
    L = [v for v in P.pool if v.kind in ("ints", "strs") and (v.n is None or v.n >= 2)]
    if kind == "guard" and L:
        hdr = f"if len({rng.choice(L).name}) > 1:"
    else:
        hdr = f"for _ in range({rng.randint(2, 3)}):"
    P.lines.extend([hdr] + ["    " + l for l in inner])
    return True


# ---------------------------------------------------------------- input and output
TOK_CAP, ROW_CAP, TOTAL_CAP, DIG_CAP = 24, 30, 60, 9   # largest input shape G2 reproduces; real inputs above it are capped


def _isint(x):
    try: int(x); return True
    except ValueError: return False


def _block_line(toks):
    if toks and all(_isint(t) for t in toks):
        return {"kind": "ints", "digs": [min(DIG_CAP, max(1, len(t.lstrip("-")))) for t in toks], "neg": any(t.startswith("-") for t in toks)}
    return {"kind": "strs", "digs": [max(1, min(8, len(t))) for t in toks] or [1], "neg": False}


def sample_stdin(rng, real_in):
    """Stdin spec with the real input's shape: lines, tokens per line, int vs text, digit length, and the common
    'count on the first line' pattern. Values are NOT copied. Shapes above the caps are capped (reported in the paper)."""
    L = [l.split() for l in real_in.strip("\n").split("\n")] if real_in.strip() else []
    if not L: return []
    spec, i = [], 0
    hdr = len(L[0]) == 1 and _isint(L[0][0])
    if len(L) > 4:                                   # a table of rows, with or without a count header
        if hdr:
            spec.append({"kind": "ints", "digs": [1], "neg": False, "hdr": True}); i = 1
        row = L[i] if i < len(L) else L[-1]
        k = max(1, min(12, len(row))); rows = max(1, min(ROW_CAP, len(L) - i, TOTAL_CAP // k))
        b = _block_line(row[:k]); b.update(kind="table_" + b["kind"], rows=rows, k=k, hdr_ref=bool(hdr))
        spec.append(b)
        if hdr: spec[0]["count"] = rows
        return spec
    for j, toks in enumerate(L):
        toks = toks[:TOK_CAP] or [""]
        b = _block_line(toks)
        if j == 0 and hdr and len(L) == 2 and int(L[0][0]) == len(L[1]):
            b["hdr"] = True; b["count"] = min(len(L[1]), TOK_CAP)
        spec.append(b)
    return spec


def spec_tokens(spec):
    return sum(b["rows"] * b["k"] if b["kind"].startswith("table_") else len(b["digs"]) for b in spec)


def draw_stdin(rng, spec):
    lines = []
    for b in spec:
        if b["kind"] in ("ints", "table_ints"):
            reps = b["rows"] if b["kind"] == "table_ints" else 1
            ds = b["digs"] if b["kind"] == "ints" else b["digs"][:b["k"]]
            for _ in range(reps):
                if b.get("hdr"):
                    lines.append(str(b["count"])); continue
                vals = []
                pool = None
                if len(ds) >= 4 and rng.random() < 0.5:
                    pool = [rng.randint(10 ** (d - 1) if d > 1 else 0, 10 ** d - 1) for d in ds[:max(2, int(0.6 * len(ds)))]]
                for d in ds:
                    v = rng.choice(pool) if pool else rng.randint(10 ** (d - 1) if d > 1 else 0, 10 ** d - 1)
                    if b["neg"] and rng.random() < 0.3: v = -v
                    vals.append(v)
                lines.append(" ".join(map(str, vals)))
        else:
            reps = b["rows"] if b["kind"] == "table_strs" else 1
            ds = b["digs"]
            for _ in range(reps):
                lines.append(" ".join("".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(d)) for d in ds))
    return "\n".join(lines) + ("\n" if lines else "")


def emit_readers(P, spec):
    rng = P.rng
    allint = bool(spec) and all(b["kind"] in ("ints", "table_ints") for b in spec)
    if allint and rng.random() < 0.15:
        P.imports.add("import sys")
        ntok = spec_tokens(spec)
        d = P.add("list", "strs", derived=False, n=ntok); n = P.add("list", "ints", derived=False, n=ntok)
        v = P.loopvar()
        P.emit(f"{d.name} = sys.stdin.read().split()", f"{n.name} = [int({v}) for {v} in {d.name}]")
        d.used = True
        return
    if not spec:
        ln = rng.randint(3, 6)
        L = P.add("list", "ints", derived=False, n=ln)
        P.emit(f"{L.name} = {[rng.randint(1, 60) for _ in range(ln)]}")
        return
    hdr_var = None
    for b in spec:
        kind, k = b["kind"], len(b["digs"])
        if kind == "ints":
            if k == 1:
                v = P.add("scalar", "int", derived=False); P.emit(f"{v.name} = int(input())")
                if b.get("hdr"): hdr_var = v
            elif k <= 3 and rng.random() < 0.5:
                vs = [P.add("scalar", "int", derived=False) for _ in range(k)]
                P.emit(f"{', '.join(v.name for v in vs)} = map(int, input().split())")
            else:
                v = P.add("list", "ints", derived=False, n=k); P.emit(f"{v.name} = list(map(int, input().split()))")
        elif kind == "strs":
            if k == 1:
                v = P.add("str", "str", derived=False); P.emit(f"{v.name} = input()")
            else:
                v = P.add("strs", "strs", derived=False, n=k); P.emit(f"{v.name} = input().split()")
        else:                                         # table of rows
            cnt = hdr_var.name if (b.get("hdr_ref") and hdr_var is not None) else str(b["rows"])
            if hdr_var is not None and b.get("hdr_ref"): hdr_var.used = True
            x = P.loopvar()
            if kind == "table_ints":
                v = P.add("list", "ints", derived=False, n=b["rows"] * b["k"])
                if b["k"] == 1: P.emit(f"{v.name} = [int(input()) for _ in range({cnt})]")
                else: P.emit(f"{v.name} = [int({x}) for _ in range({cnt}) for {x} in input().split()]")
            else:
                v = P.add("strs", "strs", derived=False, n=b["rows"] * b["k"])
                if b["k"] == 1: P.emit(f"{v.name} = [input() for _ in range({cnt})]")
                else: P.emit(f"{v.name} = [{x} for _ in range({cnt}) for {x} in input().split()]")


def fold_expr(P, rest):
    """Integer expression that reads every leftover variable."""
    parts = []
    for v in rest:
        v.used = True
        parts.append({"int": v.name, "ints": f"sum({v.name})", "str": f"len({v.name})", "strs": f"len({v.name})",
                      "dict": f"len({v.name})", "func": f"{v.name}(1)"}[v.kind])
    return " + ".join(parts)


def emit_output(P, shape):
    rng = P.rng
    for fv in [v for v in P.pool if v.kind == "func" and not v.used]:   # a helper that was defined must be called on real data
        arg = P.pick("int")
        if arg is not None:
            t = P.add("acc", "int"); P.emit(f"{t.name} = {fv.name}({arg.name})"); fv.used = True
    left = [v for v in P.pool if not v.used]
    if not left:
        left = [v for v in P.pool if v.derived] or P.pool
    if shape == 1:
        if len(left) == 1 and left[0].kind in ("int", "str"):
            P.emit(f"print({left[0].name})"); left[0].used = True
        elif all(v.kind == "int" for v in left) and rng.random() < 0.2:
            yes, no = rng.choice([("Yes", "No"), ("YES", "NO"), ("OK", "NG"), ("even", "odd")])
            P.emit(f'print("{yes}" if ({fold_expr(P, left)}) % 2 == 0 else "{no}")')
        elif all(v.kind == "int" for v in left) and rng.random() < 0.5:
            P.emit(f"print({fold_expr(P, left)})")
        else:
            args = []
            for v in left:
                v.used = True
                args.append({"int": v.name, "str": v.name, "ints": f"sum({v.name})", "strs": f"len({v.name})",
                             "dict": f"len({v.name})", "func": f"{v.name}(1)"}[v.kind])
            P.emit(f"print({', '.join(args)})")
    elif shape == 2:
        lists = [v for v in left if v.kind in ("ints", "strs")] or [v for v in P.pool if v.kind in ("ints", "strs") and v.derived]
        rest = [v for v in left if v not in lists[:1]]
        if lists:
            L = lists[0]; L.used = True; x = P.loopvar()
            form_ = rng.choice(["loop", "star", "join"])
            if form_ == "loop": P.emit(f"for {x} in {L.name}:", f"    print({x})")
            elif form_ == "star": P.emit(f"print(*{L.name}, sep=\"\\n\")")
            else: P.emit(f"print(\"\\n\".join(map(str, {L.name})))")
            if rest: P.emit(f"print({fold_expr(P, rest)})")
        else:
            for v in left:
                v.used = True
                P.emit(f"print({v.name if v.kind in ('int', 'str') else fold_expr(P, [v])})")
            if len(left) < 2:
                x = P.loopvar(); base = left[0].name if left and left[0].kind == "int" else "0"
                P.emit(f"for {x} in range({lit(rng, 2, 4)}):", f"    print({base} + {x})")
    else:  # shape 0: a data-dependent guard that does not fire
        e = fold_expr(P, left)
        P.emit(f"if {e} < -999999999:", f"    print({e})")


def liveness_ok(code):
    t = ast.parse(code)
    stored, loaded = set(), set()
    for n in ast.walk(t):
        if isinstance(n, ast.Name):
            (stored if isinstance(n.ctx, ast.Store) else loaded).add(n.id)
        elif isinstance(n, ast.arg):
            stored.add(n.arg)
    dead = {x for x in stored - loaded if x != "_"}
    return not dead, sorted(dead)


# ---------------------------------------------------------------- matching
TOL = [  # level 0 strict, level 1 relaxed
    dict(lines=lambda L: max(1, round(0.10 * L)), cc=lambda c: max(1, round(0.15 * c)), depth=0, nlen=1.0, single=0.20),
    dict(lines=lambda L: max(2, round(0.20 * L)), cc=lambda c: max(2, round(0.30 * c)), depth=1, nlen=2.0, single=0.35),
]


NAME_LEN_SHIFT, NAME_SINGLE_SHIFT, BEST_OF = 0.6, 0.0, 4   # calibration measured on synthetic targets (first-accepted programs ran 0.3-0.6 short on name length); best-of-4 selection


def style_mix(nlen, single=0.5):
    if single >= 0.9:
        return {"terse": 0.98, "mixed": 0.01, "long": 0.01}
    terse = min(1.0, max(0.0, (3.5 - nlen) / 2.5)); long_ = min(1.0, max(0.0, (nlen - 4.0) / 4.0))
    mixed = max(0.05, 1.0 - terse - long_)
    return {"terse": terse + 0.02, "mixed": mixed, "long": long_ + 0.02}



# ---------------------------------------------------------------- depth steering (v3)
def _top_boundaries(lines, base):
    """Indices >= base of top-level statement starts (column 0, not a continuation of an if/try block)."""
    out = []
    for i in range(base, len(lines)):
        l = lines[i]
        if l and not l[0].isspace() and not l.startswith(("else", "elif", "except", "finally")):
            out.append(i)
    return out


def deepen(P, base, tgt_depth, guard_vars, max_loops=2):
    """Wrap a suffix of the program body in an always-true guard, a try/except, or a short loop until the nesting depth reaches the target.
    A guard tests an input-reader variable known to hold at least two items (five spellings, never repeated); a loop is `for _ in range(2 or 3)` (at most two).
    The wrapped suffix always runs, so liveness and the output are unaffected."""
    rng = P.rng
    loops = 0
    for _ in range(14):
        cur = code_features("\n".join(P.lines) + "\npass")["depth"] if P.lines else 0
        if cur >= tgt_depth: return True
        L = guard_vars   # variables defined by the input readers, so they exist before any wrapped statement
        starts = _top_boundaries(P.lines, base)
        if not starts: return False
        rng.shuffle(starts)
        starts = sorted(starts[:4]) + [base]
        used = {l.strip() for l in P.lines}
        done = False
        for st in starts:
            r = rng.random()
            before, after, is_loop = None, [], False
            if L and loops >= 0 and r < 0.55:
                v = rng.choice(L).name
                for hdr in rng.sample([f"if {v}:", f"if len({v}) > 0:", f"if len({v}) > 1:", f"if len({v}) >= 2:", f"if len({v}) != 0:"], 5):
                    if hdr not in used: before = [hdr]; break
            elif r < 0.67:
                before, after = ["try:"], ["except Exception:", "    pass"]
            if before is None and loops < max_loops:
                hdr = f"for _ in range({rng.randint(2, 3)}):"
                before = [hdr]; is_loop = True
            if before is None: continue
            trial = P.lines[:st] + before + ["    " + l for l in P.lines[st:]] + after
            d = code_features("\n".join(trial) + "\npass")["depth"]
            if d > cur:
                P.lines = trial; loops += is_loop; done = True; break
        if not done: return False
    return False


def build(rng, tgt, spec, p_indep):
    P = Prog(rng, style_mix(tgt["name_len_mean"] + NAME_LEN_SHIFT, max(0.0, tgt["name_single_frac"] + NAME_SINGLE_SHIFT)), p_indep)
    emit_readers(P, spec)
    base = len(P.lines)
    guard_vars = [v for v in P.pool if v.kind in ("ints", "strs") and (v.n is None or v.n >= 2)]
    reserve = {0: 2, 1: 1, 2: 2}[tgt["out_shape"]]
    wrap_res = min(max(0, tgt["depth"] - 3), 8)   # lines and cc kept back for the guards that deepen() adds
    for _ in range(60):
        cur = code_features("\n".join(P.lines) + "\npass") if P.lines else {"lines": 0, "cc": 1, "depth": 0}
        rem_l = tgt["lines"] - (cur["lines"] - 1) - reserve - len(P.imports) - wrap_res
        if rem_l <= 0: break
        rem_c = tgt["cc"] - cur["cc"] - wrap_res
        cand = [e for e in applicable(P) if e[2] <= rem_l + 1]
        if not cand: break
        w = []
        for name, need, lines, cc, depth, wt, fn in cand:
            s = wt
            if rem_c > 0 and cc > 0: s *= 1 + min(cc, rem_c)
            if rem_c <= 0 and cc > 0: s *= 0.15
            if depth > tgt["depth"] - 0 + 1: s *= 0.1
            if lines > rem_l: s *= 0.4
            w.append(s)
        if cur["depth"] < tgt["depth"] and rem_c >= 2 and rem_l >= 3 and rng.random() < 0.12:
            if apply_wrapped(P, cand, 1): continue
        apply_form(P, rng.choices(cand, weights=w)[0])
    deepen(P, base, tgt["depth"], guard_vars)
    emit_output(P, tgt["out_shape"])
    return P


def match_ok(tgt, f, lvl):
    t = TOL[lvl]
    return (abs(f["lines"] - tgt["lines"]) <= t["lines"](tgt["lines"]) and abs(f["cc"] - tgt["cc"]) <= t["cc"](tgt["cc"])
            and abs(f["depth"] - tgt["depth"]) <= t["depth"] and abs(f["name_len_mean"] - tgt["name_len_mean"]) <= t["nlen"]
            and abs(f["name_single_frac"] - tgt["name_single_frac"]) <= t["single"])


def generate_one(sample_index, real_code, real_in, args):
    tgt_f = code_features(real_code)
    real_out, err = run_code(real_code, real_in, **REAL_LIMITS)
    if err: return {"sample_index": sample_index, "status": "real_failed:" + err}
    tgt = dict(tgt_f); tgt["out_shape"] = stdout_features(real_out)["out_shape"]
    spec = sample_stdin(None, real_in)
    best = None
    why = collections.Counter()
    cands = []
    for attempt in range(args.max_attempts):
        rng = random.Random(f"{args.seed}-{sample_index}-{attempt}")
        try:
            P = build(rng, tgt, spec, p_indep=args.p_indep)
            code = norm(P.src())
        except Exception:
            why["build_exception"] += 1; continue
        f = code_features(code)
        lvl = 0 if match_ok(tgt, f, 0) else (1 if match_ok(tgt, f, 1) else None)
        if lvl is None:
            t = TOL[1]
            for key, bad in (("lines", abs(f["lines"] - tgt["lines"]) > t["lines"](tgt["lines"])), ("cc", abs(f["cc"] - tgt["cc"]) > t["cc"](tgt["cc"])),
                             ("depth", abs(f["depth"] - tgt["depth"]) > t["depth"]), ("name_len", abs(f["name_len_mean"] - tgt["name_len_mean"]) > t["nlen"]),
                             ("name_single", abs(f["name_single_frac"] - tgt["name_single_frac"]) > t["single"])):
                if bad: why["miss_" + key] += 1
            continue
        ok, dead = liveness_ok(code)
        if not ok: why["dead_store"] += 1; continue
        cases = []
        for c in range(3):
            cases.append(draw_stdin(random.Random(f"{args.seed}-{sample_index}-{attempt}-in{c}"), spec))
        outs = [run_code(code, s) for s in cases]
        if any(e for _, e in outs): why["run_error"] += 1; continue
        if stdout_features(outs[0][0])["out_shape"] != tgt["out_shape"]: why["wrong_shape"] += 1; continue
        if run_code(code, cases[0])[0] != outs[0][0]: why["nondeterministic"] += 1; continue
        if tgt["out_shape"] != 0 and len(set(o for o, _ in outs)) == 1 and spec: why["input_independent"] += 1; continue  # output must depend on the input
        if norm(real_code) == code: why["equals_real"] += 1; continue
        rec = {"sample_index": sample_index, "status": "ok", "tol_level": lvl, "attempts": attempt + 1, "source_code": code,
               "stdin_cases": cases, "target": {k: tgt[k] for k in ("lines", "cc", "depth", "name_len_mean", "name_single_frac", "out_shape")},
               "achieved": {k: f[k] for k in ("lines", "cc", "depth", "name_len_mean", "name_single_frac")},
               "out_first": outs[0][0].split("\n")[0] if outs[0][0] else ""}
        if lvl == 0:
            t0 = TOL[0]
            rec["score"] = (abs(f["lines"] - tgt["lines"]) / t0["lines"](tgt["lines"]) + abs(f["cc"] - tgt["cc"]) / t0["cc"](tgt["cc"])
                            + abs(f["name_len_mean"] - tgt["name_len_mean"]) / t0["nlen"] + abs(f["name_single_frac"] - tgt["name_single_frac"]) / t0["single"])
            cands.append(rec)
            if len(cands) >= BEST_OF: break
            continue
        if best is None: best = rec
    if cands:
        r = min(cands, key=lambda x: x["score"]); r["n_candidates"] = len(cands); return r
    return best or {"sample_index": sample_index, "status": "unmatched", "attempts": args.max_attempts, "why": dict(why),
                    "target": {k: tgt[k] for k in ("lines", "cc", "depth", "name_len_mean", "name_single_frac", "out_shape")}}


def _work(t):
    idx, pid, code, real_in, args = t
    r = generate_one(idx, code, real_in, args)
    r["problem_id"] = pid
    return r


def selftest():
    bad = 0
    for name, need, lines, cc, depth, w, fn in FORMS:
        P = Prog(random.Random(1), {"terse": 0, "mixed": 1, "long": 0}, 1.0)
        for k in sorted(set(need)):
            for _ in range(need.count(k)): P.add("scalar" if k == "int" else "list", k, derived=False)
        if name in TARGET_FORMS:
            P.pool.append(Var("tgt_", "int", True))
        if "func" in need:
            P.pool = [v for v in P.pool if v.kind != "func"]; P.pool.append(Var("fn_", "func", False)); P.emit("def fn_(x):", "    return x")
        base = len(P.lines)
        ops = [P.pick(k) for k in need]
        a = ops[0] if ops else None; b = ops[1] if len(ops) > 1 else a
        fn(P, a, b)
        body = P.lines[base:]
        code = "\n".join(["import sys"] + [f"{v.name} = {'0' if v.kind == 'int' else '[0]' if v.kind in ('ints', 'strs') else repr('ab')}" for v in P.pool if v.kind in ('int', 'ints', 'str', 'strs')] + body)
        f0 = code_features("\n".join(["import sys"] + [f"{v.name} = {'0' if v.kind == 'int' else '[0]' if v.kind in ('ints', 'strs') else repr('ab')}" for v in P.pool if v.kind in ('int', 'ints', 'str', 'strs')] + ["pass"]))
        f1 = code_features(code)
        got = (len(body), f1["cc"] - f0["cc"], f1["depth"] - f0["depth"])
        if got != (lines, cc, depth):
            bad += 1; print("MISMATCH", name, "declared", (lines, cc, depth), "measured", got)
    print("forms:", len(FORMS), "mismatches:", bad)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="manifest_confirm.json"); ap.add_argument("--out", default="g2_base.json")
    ap.add_argument("--seed", type=int, default=MASTER_SEED); ap.add_argument("--max-attempts", type=int, default=400)
    ap.add_argument("--p-indep", type=float, default=0.6); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--selftest", action="store_true"); ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    if args.selftest: sys.exit(1 if selftest() else 0)
    man = json.load(open(args.manifest))["samples"]
    mh = hashlib.sha256(open(args.manifest, "rb").read()).hexdigest()
    tasks = []
    for s in (man[:args.limit] if args.limit else man):
        c1 = next(b for b in s["conditions"] if b["condition_id"] == 1)
        real_in = (c1.get("stdin_cases") or s.get("stdin_cases"))[0]
        tasks.append((s["sample_index"], s.get("problem_id"), c1["source_code"], real_in, args))
    recs = []
    import multiprocessing as mp
    with mp.Pool(args.jobs) as pool:
        for r in pool.imap(_work, tasks, chunksize=4):
            recs.append(r)
            if len(recs) % 100 == 0: print(len(recs), "done", file=sys.stderr)
    st = collections.Counter(r["status"] if r["status"] != "ok" else f"ok_level{r['tol_level']}" for r in recs)
    why = collections.Counter()
    for r in recs:
        for k, v in r.get("why", {}).items(): why[k] += v
    n_ok = sum(1 for r in recs if r["status"] == "ok")
    rep = {"gate_A_coverage": n_ok / max(1, len(recs)), "gate_A_pass": n_ok / max(1, len(recs)) >= 0.95,
           "unmatched_attempt_failures": dict(why), "manifest_sha256": mh, "seed": args.seed, "p_indep": args.p_indep, "max_attempts": args.max_attempts, "n": len(recs), "status": dict(st),
           "mean_attempts": sum(r.get("attempts", 0) for r in recs) / max(1, len(recs))}
    json.dump({"manifest_sha256": mh, "seed": args.seed, "samples": recs}, open(args.out, "w"))
    json.dump(rep, open("g2_report.json", "w"), indent=1); print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
