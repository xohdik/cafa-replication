#!/usr/bin/env python3
"""g2_features.py -- covariates of a Python program and of its stdin/stdout, shared by g2_generate.py and g2_balance.py.
One definition is used for real, G1 and G2 programs, so differences between them are not artifacts of different measures.
Everything is computed on ast.unparse(ast.parse(src)), the form every CAFA condition is normalised to."""
import ast
import builtins
import os
import resource
import subprocess
import sys
import tempfile

BUILTINS = set(dir(builtins))


def norm(src):
    return ast.unparse(ast.parse(src))


def user_names(tree):
    """Names the programmer chose: assigned/loop/argument/function names (not builtins, not imported modules)."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
    return {x for x in out if x not in BUILTINS}


COMPOUND = (ast.For, ast.While, ast.If, ast.FunctionDef, ast.With, ast.Try)


def depth_of(node, d=0):
    best = d
    for c in ast.iter_child_nodes(node):
        best = max(best, depth_of(c, d + 1 if isinstance(c, COMPOUND) else d))
    return best


def complexity(tree):
    cc = 1
    for n in ast.walk(tree):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.IfExp, ast.ExceptHandler, ast.AsyncFor)):
            cc += 1
        elif isinstance(n, ast.BoolOp):
            cc += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            cc += 1 + len(n.ifs)
    return cc


def code_features(src):
    code = norm(src)
    t = ast.parse(code)
    names = sorted(user_names(t))
    nodes = list(ast.walk(t))
    stmts = [n for n in nodes if isinstance(n, ast.stmt)]
    consts = [n.value for n in nodes if isinstance(n, ast.Constant)]
    return {
        "lines": len([l for l in code.splitlines() if l.strip()]),
        "stmts": len(stmts),
        "ast_nodes": len(nodes),
        "cc": complexity(t),
        "depth": depth_of(t),
        "loops": sum(isinstance(n, (ast.For, ast.While)) for n in nodes),
        "ifs": sum(isinstance(n, (ast.If, ast.IfExp)) for n in nodes),
        "comps": sum(isinstance(n, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)) for n in nodes),
        "has_func": int(any(isinstance(n, ast.FunctionDef) for n in nodes)),
        "has_import": int(any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes)),
        "n_input_calls": sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "input" for n in nodes),
        "uses_stdin_read": int("sys.stdin" in code),
        "n_names": len(names),
        "name_len_mean": (sum(map(len, names)) / len(names)) if names else 0.0,
        "name_single_frac": (sum(len(x) == 1 for x in names) / len(names)) if names else 0.0,
        "name_snake_frac": (sum("_" in x.strip("_") for x in names) / len(names)) if names else 0.0,
        "name_underscore_lead": sum(x.startswith("_") for x in names),
        "n_int_consts": sum(isinstance(c, int) and not isinstance(c, bool) for c in consts),
        "n_str_consts": sum(isinstance(c, str) for c in consts),
        "max_int_const": max([abs(c) for c in consts if isinstance(c, int) and not isinstance(c, bool)] + [0]),
        "chars": len(code),
    }


def stdin_features(stdin):
    lines = stdin.strip("\n").split("\n") if stdin.strip() else []
    toks = [l.split() for l in lines]
    def isint(x):
        try:
            int(x); return True
        except ValueError:
            return False
    all_t = [t for l in toks for t in l]
    ints = [int(t) for t in all_t if isint(t)]
    import math
    return {
        "in_lines": len(lines),
        "in_tokens": len(all_t),
        "log_in_lines": math.log1p(len(lines)),
        "log_in_tokens": math.log1p(len(all_t)),
        "in_int_frac": (len(ints) / len(all_t)) if all_t else 0.0,
        "in_max_abs": max([abs(i) for i in ints] + [0]),
        "in_mean_digits": (sum(len(str(abs(i))) for i in ints) / len(ints)) if ints else 0.0,
        "in_has_neg": int(any(i < 0 for i in ints)),
        "in_distinct_tokens_frac": (len(set(all_t)) / len(all_t)) if all_t else 0.0,
    }


def stdout_features(out):
    lines = [l for l in out.split("\n")] if out is not None else []
    while lines and lines[-1] == "":
        lines.pop()
    toks = [t for l in lines for t in l.split()]
    def isint(x):
        try:
            int(x); return True
        except ValueError:
            return False
    ints = [int(t) for t in toks if isint(t)]
    return {
        "out_lines": len(lines),
        "out_shape": 0 if not lines else (1 if len(lines) == 1 else 2),
        "out_tokens": len(toks),
        "out_int_frac": (len(ints) / len(toks)) if toks else 0.0,
        "out_first_len": len(lines[0]) if lines else 0,
        "out_max_abs": max([abs(i) for i in ints] + [0]),
        "out_first_is_10": int(bool(lines) and lines[0].strip() == "10"),
    }


REAL_LIMITS = dict(timeout=20.0, mem_mb=16384)   # real and G1 programs ran under the paper's harness; do not judge them by G2's tight limits


def run_code(src, stdin, timeout=3.0, mem_mb=1024):
    """Run src on stdin in a fresh interpreter with CPU and memory limits. Returns (stdout, error_or_None)."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "p.py")
        open(p, "w").write(src)
        def lim():
            resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
            resource.setrlimit(resource.RLIMIT_CPU, (int(timeout) + 1, int(timeout) + 1))
        try:
            r = subprocess.run([sys.executable, "-I", p], input=stdin, capture_output=True, text=True, timeout=timeout,
                               preexec_fn=lim, cwd=d, env={"PYTHONHASHSEED": "0", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        except subprocess.TimeoutExpired:
            return None, "timeout"
        if r.returncode != 0:
            return None, "exit%d" % r.returncode
        return r.stdout, None
