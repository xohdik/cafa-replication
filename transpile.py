"""
X4 operator: cross-language rewrite, with test-suite-equivalence validation.

Design per RESEARCH_PLAN.md / stubs.py TranspileOperator contract: translation
itself is pluggable (inject whatever LLM call you're using on the R740 --
Anthropic API, DeepSeek, a local model) because that's infrastructure, not the
hard part. The hard part, and the actual engineering content of this file, is
validate(): confirming a translation is behaviorally equivalent BEFORE it's
allowed into the dataset. A silently-broken transpilation that gets scored as
a semantic-reasoning failure biases S_i(language) upward for reasons that have
nothing to do with the model under test -- this is what RESEARCH_PLAN.md 7
flags as the main risk, and it's the thing this file exists to prevent.

Design choice: require caller-supplied test inputs rather than auto-generating
them blind. Auto-generated inputs for an unknown function signature are
unreliable (wrong arity, wrong types); your benchmarks (HumanEvalFix etc.)
already ship test cases -- use those.
"""
import json
import subprocess
import tempfile
import os
from dataclasses import dataclass, field


PY_HARNESS = """
import json, sys
{code}
args = json.loads(sys.argv[1])
result = {func}(*args)
print(json.dumps(result))
"""

JS_HARNESS = """
{code}
const args = JSON.parse(process.argv[2]);
const result = {func}(...args);
console.log(JSON.stringify(result));
"""

RUNNERS = {
    "python": {"harness": PY_HARNESS, "ext": ".py", "cmd": lambda path, argjson: ["python3", path, argjson]},
    "javascript": {"harness": JS_HARNESS, "ext": ".js", "cmd": lambda path, argjson: ["node", path, argjson]},
}


@dataclass
class ValidationResult:
    passed: bool
    n_total: int
    n_matched: int
    per_input: list = field(default_factory=list)   # [{input, source_output, target_output, match, error}]

    def summary(self) -> str:
        return f"{self.n_matched}/{self.n_total} test inputs matched" + ("" if self.passed else " -- REJECT")


def _run_snippet(lang: str, code: str, func_name: str, args: list, timeout: float = 5.0):
    if lang not in RUNNERS:
        raise ValueError(f"Unsupported language for execution: {lang}. "
                          f"Supported: {list(RUNNERS)}. Add a RUNNERS entry to extend.")
    spec = RUNNERS[lang]
    harness = spec["harness"].format(code=code, func=func_name)
    with tempfile.NamedTemporaryFile("w", suffix=spec["ext"], delete=False) as f:
        f.write(harness)
        path = f.name
    try:
        argjson = json.dumps(args)
        proc = subprocess.run(spec["cmd"](path, argjson), capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            return None, proc.stderr.strip()[:500]
        return json.loads(proc.stdout.strip()), None
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    except json.JSONDecodeError as e:
        return None, f"non-JSON output: {e}"
    except Exception as e:
        return None, str(e)
    finally:
        os.unlink(path)


def validate_equivalence(source_code: str, target_code: str, func_name: str,
                          test_inputs: list, source_lang: str = "python",
                          target_lang: str = "javascript", timeout: float = 5.0) -> ValidationResult:
    """
    test_inputs: list of argument lists, e.g. [[3, 5], [0, 0], [-1, 2]] for a
    two-argument function. Pull these from the benchmark's existing test
    cases rather than generating blind.
    """
    per_input = []
    n_matched = 0
    for args in test_inputs:
        src_out, src_err = _run_snippet(source_lang, source_code, func_name, args, timeout)
        tgt_out, tgt_err = _run_snippet(target_lang, target_code, func_name, args, timeout)

        if src_err is not None:
            # Source itself doesn't run -- not a transpilation problem, flag separately.
            per_input.append({"input": args, "source_output": None, "target_output": None,
                               "match": False, "error": f"source execution failed: {src_err}"})
            continue

        match = (src_err is None and tgt_err is None and src_out == tgt_out)
        if match:
            n_matched += 1
        per_input.append({
            "input": args, "source_output": src_out, "target_output": tgt_out,
            "match": match,
            "error": tgt_err if tgt_err else None,
        })

    n_total = len(test_inputs)
    # Require ALL supplied test inputs to match -- partial equivalence is not
    # equivalence for this purpose; a translation that's right on 4/5 cases is
    # still a broken translation for the one case that matters.
    passed = n_total > 0 and n_matched == n_total
    return ValidationResult(passed=passed, n_total=n_total, n_matched=n_matched, per_input=per_input)


def transpile_and_validate(source_code: str, func_name: str, test_inputs: list,
                            translate_fn, source_lang: str = "python",
                            target_lang: str = "javascript", max_attempts: int = 3):
    """
    translate_fn: callable(prompt: str) -> str -- your actual LLM call,
    injected by the caller. Not implemented here; that part is
    infrastructure (which API, which model, your auth), not methodology.

    Returns (target_code, ValidationResult) on success, or (None, last_result)
    after max_attempts failed validations -- caller must redraw the sample
    rather than keep a broken transpilation in the dataset (RESEARCH_PLAN.md 7).
    """
    prompt_template = (
        f"Translate the following {source_lang} function to {target_lang}. "
        f"Preserve the exact function name `{func_name}` and behavior. "
        f"Output ONLY the translated code, no explanation, no markdown fences.\n\n{{code}}"
    )
    last_result = None
    for attempt in range(max_attempts):
        target_code = translate_fn(prompt_template.format(code=source_code))
        target_code = _strip_markdown_fences(target_code)
        result = validate_equivalence(source_code, target_code, func_name,
                                       test_inputs, source_lang, target_lang)
        last_result = result
        if result.passed:
            return target_code, result
    return None, last_result


def transpile_and_validate_hybrid(source_code: str, func_name: str, test_inputs: list,
                                   primary_translate_fn, fallback_translate_fn=None,
                                   source_lang: str = "python", target_lang: str = "javascript",
                                   primary_attempts: int = 3, fallback_attempts: int = 2):
    """
    Cost-aware two-tier transpilation: try the free/local model first
    (primary_translate_fn -- e.g. your R740's llama.cpp/GGUF model), and
    only escalate to a paid API (fallback_translate_fn) for the samples the
    local model genuinely can't handle after primary_attempts retries. This
    keeps API spend proportional to the hard cases, not the whole sample
    pool -- for a TSE-scale sweep (hundreds of runs) the difference between
    "pay for everything" and "pay only for local-model failures" is real.

    Returns (target_code, ValidationResult, tier) where tier is
    "primary", "fallback", or None. None means total failure -- log and
    skip this sample rather than keep a broken transpilation (do NOT
    silently substitute a failed translation; that reintroduces exactly
    the confound this whole validator exists to prevent).
    """
    target_code, result = transpile_and_validate(
        source_code, func_name, test_inputs, primary_translate_fn,
        source_lang, target_lang, max_attempts=primary_attempts)
    if target_code is not None:
        return target_code, result, "primary"

    if fallback_translate_fn is None:
        return None, result, None

    target_code, result = transpile_and_validate(
        source_code, func_name, test_inputs, fallback_translate_fn,
        source_lang, target_lang, max_attempts=fallback_attempts)
    if target_code is not None:
        return target_code, result, "fallback"

    return None, result, None


def hybrid_transpile_pool(samples: list, primary_translate_fn, fallback_translate_fn=None,
                           source_lang: str = "python", target_lang: str = "javascript",
                           primary_attempts: int = 3, fallback_attempts: int = 2) -> dict:
    """
    samples: list of {"source_code", "func_name", "test_inputs"} dicts.
    Runs the hybrid pipeline over the whole pool and returns summary stats
    -- report these in the paper (Section VII/VIII) rather than just the
    per-sample results, since "what fraction needed the paid fallback" is
    itself a useful cost/quality datapoint for the engineering plan.
    """
    results = []
    for s in samples:
        target_code, result, tier = transpile_and_validate_hybrid(
            s["source_code"], s["func_name"], s["test_inputs"],
            primary_translate_fn, fallback_translate_fn,
            source_lang, target_lang, primary_attempts, fallback_attempts)
        results.append({"sample": s, "target_code": target_code, "result": result, "tier": tier})

    n = len(samples)
    n_primary = sum(1 for r in results if r["tier"] == "primary")
    n_fallback = sum(1 for r in results if r["tier"] == "fallback")
    n_failed = sum(1 for r in results if r["tier"] is None)
    return {
        "results": results,
        "n_total": n,
        "n_primary_success": n_primary,
        "n_fallback_success": n_fallback,
        "n_total_failure": n_failed,
        "primary_success_rate": n_primary / n if n else 0.0,
        "fallback_invocation_rate": (n_fallback + n_failed) / n if n else 0.0,  # proxy for API spend
    }


def _script_harness(lang: str, code: str) -> str:
    """Wrap translated code so a whole-program stdin->stdout comparison works."""
    return code


SCRIPT_RUNNERS = {
    "python": {"ext": ".py", "cmd": lambda p: ["python3", p]},
    "javascript": {"ext": ".js", "cmd": lambda p: ["node", p]},
}


def _run_script_lang(lang: str, code: str, stdin_text: str, timeout: float = 5.0):
    if lang not in SCRIPT_RUNNERS:
        raise ValueError(f"Unsupported script language: {lang}")
    spec = SCRIPT_RUNNERS[lang]
    with tempfile.NamedTemporaryFile("w", suffix=spec["ext"], delete=False) as f:
        f.write(code)
        path = f.name
    try:
        p = subprocess.run(spec["cmd"](path), input=stdin_text,
                            capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            return None, p.stderr.strip()[:400]
        return p.stdout, None
    except Exception as e:
        return None, str(e)
    finally:
        os.unlink(path)


def validate_script_equivalence(source_code: str, target_code: str,
                                 stdin_cases: list, source_lang: str = "python",
                                 target_lang: str = "javascript",
                                 timeout: float = 5.0) -> ValidationResult:
    """Whole-program equivalence: same stdin must produce same stdout.

    Needed because most competitive-programming corpora (CodeNet included) are
    top-level scripts with no function to call -- roughly 58% of one real pool.
    A function-only validator silently SKIPS all of those, which showed up in
    the manifest audit as X4 coverage of exactly 0% on real samples while
    synthetic samples were at least attempted.

    stdout is compared after stripping trailing whitespace per line, since
    languages differ in trailing-newline conventions and that is not a
    semantic difference."""
    def norm(s):
        return "\n".join(line.rstrip() for line in s.rstrip().splitlines())

    per_input, n_matched = [], 0
    for stdin_text in stdin_cases:
        src_out, src_err = _run_script_lang(source_lang, source_code, stdin_text, timeout)
        tgt_out, tgt_err = _run_script_lang(target_lang, target_code, stdin_text, timeout)

        if src_err is not None:
            per_input.append({"input": stdin_text[:60], "source_output": None,
                               "target_output": None, "match": False,
                               "error": f"source execution failed: {src_err}"})
            continue

        match = (tgt_err is None and norm(src_out) == norm(tgt_out))
        if match:
            n_matched += 1
        per_input.append({"input": stdin_text[:60],
                           "source_output": (src_out or "")[:120],
                           "target_output": (tgt_out or "")[:120],
                           "match": match, "error": tgt_err})

    n_total = len(stdin_cases)
    return ValidationResult(passed=(n_total > 0 and n_matched == n_total),
                             n_total=n_total, n_matched=n_matched,
                             per_input=per_input)


def transpile_script_and_validate(source_code: str, stdin_cases: list,
                                   translate_fn, source_lang: str = "python",
                                   target_lang: str = "javascript",
                                   max_attempts: int = 3):
    """Script-mode counterpart of transpile_and_validate()."""
    prompt_template = (
        f"Translate the following complete {source_lang} program to "
        f"{target_lang}. It reads from standard input and writes to standard "
        f"output; preserve that behavior exactly, including output format. "
        f"Output ONLY the translated program, no explanation, no markdown "
        f"fences.\n\n{{code}}")
    last = None
    for _ in range(max_attempts):
        target_code = _strip_markdown_fences(translate_fn(prompt_template.format(code=source_code)))
        result = validate_script_equivalence(source_code, target_code, stdin_cases,
                                              source_lang, target_lang)
        last = result
        if result.passed:
            return target_code, result
    return None, last


def transpile_script_hybrid(source_code: str, stdin_cases: list,
                             primary_translate_fn, fallback_translate_fn=None,
                             source_lang: str = "python",
                             target_lang: str = "javascript",
                             primary_attempts: int = 3, fallback_attempts: int = 2):
    """Two-tier script transpilation, mirroring transpile_and_validate_hybrid."""
    code, result = transpile_script_and_validate(
        source_code, stdin_cases, primary_translate_fn, source_lang,
        target_lang, primary_attempts)
    if code is not None:
        return code, result, "primary"
    if fallback_translate_fn is None:
        return None, result, None
    code, result = transpile_script_and_validate(
        source_code, stdin_cases, fallback_translate_fn, source_lang,
        target_lang, fallback_attempts)
    if code is not None:
        return code, result, "fallback"
    return None, result, None


# ---- Concrete backend factories ---------------------------------------------
# Both are structurally complete but genuinely untestable in this sandbox --
# no GPU for llama.cpp, no API key/network for DeepSeek. Test the CONTROL FLOW
# above with mocks (done below in __main__); test THESE on the R740.

# Completion-style prompt for BASE (non-instruct) code models.
#
# WHY THIS SHAPE. The first version issued an instruction ("Output ONLY the
# translated code...") and set stop=["\n\n\n"]. Both were wrong for a base
# model, and together they produced EMPTY output on every attempt: the prompt
# ended with a Python code block, the model's natural continuation began with
# blank lines, and the stop sequence fired before a single code token was
# emitted. Diagnosis was unambiguous -- raw output was the empty string, not
# malformed code.
#
# A base model completes patterns rather than following instructions, so the
# prompt is framed as a partially-filled translation the model finishes. The
# stop sequence is the start of the NEXT section, which the model emits once
# it considers the translation done.
# Preamble injected into every script translation. The model is shown it in
# the exemplar and told to assume it, rather than being expected to reproduce
# it: a measured failure had the model emit correct translation logic that
# referenced `_lines` without ever defining it, because it copied the
# exemplar's BODY and dropped its boilerplate. Supplying the preamble makes
# that failure impossible instead of merely less likely.
JS_STDIN_PREAMBLE = (
    'const _lines = require("fs").readFileSync(0, "utf8").split("\\n");\n'
    'let _li = 0;\n'
    'const _next = () => _lines[_li++];\n'
    # Python builtins the model reaches for in translated code. A measured
    # failure was `sum(a)` emitted verbatim into JavaScript, where it is
    # undefined. Supplying them is more reliable than instructing the model
    # not to use them.
    'const sum = (a) => a.reduce((x, y) => x + y, 0);\n'
    'const len = (a) => a.length;\n'
    'const range = (n) => Array.from({length: n}, (_, i) => i);\n'
    'const abs = Math.abs, floor = Math.floor, ceil = Math.ceil;\n'
)


# Unicode lookalikes a quantized model emits instead of ASCII operators.
# Measured: `filter(s => s)` came back as `filter(s \u21d2 s)`, which is a
# JavaScript SyntaxError. This is a decoding artifact, not a reasoning error,
# so normalizing it recovers otherwise-correct translations rather than
# masking a genuine failure.
UNICODE_FIXUPS = {
    "\u21d2": "=>",   # double arrow
    "\u2192": "=>",   # right arrow
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2260": "!=",
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u00a0": " ",    # non-breaking space
}


def normalize_unicode_operators(code: str) -> str:
    for bad, good in UNICODE_FIXUPS.items():
        code = code.replace(bad, good)
    return code

SCRIPT_COMPLETION_PROMPT = """# Translate Python to {target}.
# Each program reads from standard input and writes to standard output.
# Assume these are already defined; do NOT redefine them:
#   _lines : array of input lines
#   _next(): returns the next input line
# Python input() maps to _next().

# Python:
n = int(input())
a = list(map(int, input().split()))
print(sum(a))

# {target}:
const n = parseInt(_next());
const a = _next().trim().split(/\\s+/).filter(s => s).map(Number);
console.log(a.reduce((x, y) => x + y, 0));

# Python:
{code}

# {target}:
"""


# Python standard-library modules with no straightforward JavaScript
# equivalent. A program importing one of these cannot be faithfully
# translated by a model that must invent the missing library, and the
# measured failure mode is exactly that: `import bisect` became
# `require("./bisect.js")`, a module that does not exist.
UNTRANSLATABLE_IMPORTS = frozenset({
    "bisect", "collections", "heapq", "itertools", "functools", "fractions",
    "decimal", "re", "array", "queue", "statistics", "numpy", "scipy",
    "networkx", "copy", "operator", "string", "random",
})


def uses_untranslatable_imports(code: str) -> set:
    """Names of imported modules that have no JS counterpart."""
    import ast as _ast
    found = set()
    try:
        tree = _ast.parse(code)
    except Exception:
        return found
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root in UNTRANSLATABLE_IMPORTS:
                    found.add(root)
        elif isinstance(node, _ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in UNTRANSLATABLE_IMPORTS:
                found.add(root)
    return found


def _looks_like_script(code: str) -> bool:
    """Top-level stdin/stdout program rather than a callable function.

    The few-shot example must match the FORM being translated. A
    function-shaped exemplar applied to a stdin->stdout script teaches the
    model the wrong output shape, and the resulting translation fails
    whole-program stdout comparison even when the logic is right."""
    import ast as _ast
    try:
        tree = _ast.parse(code)
    except Exception:
        return "input(" in code or "print(" in code
    has_toplevel_stmt = any(
        not isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                            _ast.ClassDef, _ast.Import, _ast.ImportFrom))
        for n in tree.body)
    return has_toplevel_stmt


BASE_COMPLETION_PROMPT = """# Translate Python to {target}.

# Python:
def add(a, b):
    return a + b

# {target}:
function add(a, b) {{
    return a + b;
}}

# Python:
{code}

# {target}:
"""


def make_llama_cpp_translate_fn(model_path: str, n_gpu_layers: int = -1,
                                 n_ctx: int = 4096, temperature: float = 0.2,
                                 max_tokens: int = 768, base_model: bool = True,
                                 target_language: str = "JavaScript"):
    """Local, free translate_fn backed by llama.cpp.

    base_model=True (default) reformats the caller's instruction prompt into
    a few-shot completion, which is what a non-instruct code model actually
    responds to. Set base_model=False for an instruct-tuned GGUF, where the
    instruction prompt is passed through unchanged.

    Lazy-imports llama_cpp so this module does not hard-require it."""
    from llama_cpp import Llama
    llm = Llama(model_path=model_path, n_gpu_layers=n_gpu_layers,
                n_ctx=n_ctx, verbose=False)

    def translate_fn(prompt: str) -> str:
        is_script = False
        if base_model:
            # Recover the source code from the instruction prompt: everything
            # after the last blank line is the code block the caller appended.
            code = prompt.rsplit("\n\n", 1)[-1].strip()
            is_script = _looks_like_script(code)
            template = (SCRIPT_COMPLETION_PROMPT if is_script
                        else BASE_COMPLETION_PROMPT)
            text = template.format(code=code, target=target_language)
            stops = ["\n# Python:", "\n# Translate", "\n\n\n\n"]
        else:
            text = prompt
            stops = ["\n# Python:"]
        out = llm(text, max_tokens=max_tokens, temperature=temperature, stop=stops)
        body = normalize_unicode_operators(out["choices"][0]["text"])
        if is_script and target_language.lower().startswith("java"):
            body = JS_STDIN_PREAMBLE + body
        return body

    return translate_fn


def make_deepseek_translate_fn(api_key: str = None, model: str = "deepseek-chat",
                                temperature: float = 0.2):
    """Paid fallback translate_fn via DeepSeek's OpenAI-compatible API.
    Reads DEEPSEEK_API_KEY from the environment if api_key isn't passed
    explicitly -- never hardcode the key in code that might get committed."""
    import os
    import requests

    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise ValueError("No DeepSeek API key found. Pass api_key= or set DEEPSEEK_API_KEY.")

    state = {"warned": False, "n_fail": 0, "n_ok": 0}

    def translate_fn(prompt: str) -> str:
        # An API failure here (wrong key, wrong provider, rate limit) must not
        # look like a translation failure. Silently returning "" would make the
        # fallback tier appear to be working while contributing nothing, and
        # the only symptom would be an unexplained drop in retention.
        try:
            resp = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 1024,
                },
                timeout=60,
            )
            resp.raise_for_status()
            state["n_ok"] += 1
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            state["n_fail"] += 1
            if not state["warned"]:
                state["warned"] = True
                import sys as _sys
                print(f"\n*** DeepSeek fallback is FAILING: {type(e).__name__}: "
                      f"{str(e)[:200]}\n*** Every fallback call will fail. Check that "
                      f"DEEPSEEK_API_KEY belongs to DeepSeek (an OpenAI key will 401 "
                      f"here), then re-run. Continuing with local model only.\n",
                      file=_sys.stderr, flush=True)
            return ""

    translate_fn.stats = state
    return translate_fn

    return translate_fn


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


if __name__ == "__main__":
    # Real end-to-end test of the validator, no LLM needed -- one correct
    # hand-written translation, one deliberately broken one, confirming the
    # validator accepts the good case and rejects the bad case for the right
    # reason rather than just "always passes."
    source = "def add_pairs(a, b):\n    return a + b"

    correct_js = "function add_pairs(a, b) {\n    return a + b;\n}"
    broken_js = "function add_pairs(a, b) {\n    return a - b;\n}"  # wrong operator

    test_inputs = [[3, 5], [0, 0], [-1, 2], [100, -100]]

    print("=== Correct translation ===")
    result = validate_equivalence(source, correct_js, "add_pairs", test_inputs)
    print(result.summary())
    for r in result.per_input:
        print(" ", r)

    print("\n=== Broken translation (subtraction instead of addition) ===")
    result = validate_equivalence(source, broken_js, "add_pairs", test_inputs)
    print(result.summary())
    for r in result.per_input:
        print(" ", r)

    print("\n=== transpile_and_validate with a fake translate_fn (simulates an LLM that fixes itself after rejection) ===")
    attempts = {"n": 0}
    def fake_translate_fn(prompt):
        attempts["n"] += 1
        # first two attempts "hallucinate" the wrong operator, third gets it right
        if attempts["n"] < 3:
            return "```javascript\nfunction add_pairs(a, b) {\n    return a - b;\n}\n```"
        return "```javascript\nfunction add_pairs(a, b) {\n    return a + b;\n}\n```"

    target_code, result = transpile_and_validate(source, "add_pairs", test_inputs, fake_translate_fn, max_attempts=3)
    print(f"Attempts used: {attempts['n']}")
    print(f"Final result: {result.summary()}")
    print(f"Accepted code: {target_code!r}")

    print("\n=== Hybrid fallback: three scenarios ===")

    def always_correct(prompt):
        return "function add_pairs(a, b) { return a + b; }"

    def always_wrong(prompt):
        return "function add_pairs(a, b) { return a - b; }"

    # Scenario 1: primary succeeds immediately -- fallback should never be called.
    fallback_called = {"n": 0}
    def fallback_tracker_never_should_fire(prompt):
        fallback_called["n"] += 1
        return "function add_pairs(a, b) { return a + b; }"

    target_code, result, tier = transpile_and_validate_hybrid(
        source, "add_pairs", test_inputs, always_correct, fallback_tracker_never_should_fire)
    print(f"Scenario 1 (primary succeeds): tier={tier}, fallback_calls={fallback_called['n']} (expect 0)")
    assert tier == "primary" and fallback_called["n"] == 0

    # Scenario 2: primary always wrong, fallback correct -- should escalate and succeed.
    target_code, result, tier = transpile_and_validate_hybrid(
        source, "add_pairs", test_inputs, always_wrong, always_correct,
        primary_attempts=2, fallback_attempts=2)
    print(f"Scenario 2 (primary fails, fallback succeeds): tier={tier}")
    assert tier == "fallback" and target_code is not None

    # Scenario 3: both primary and fallback always wrong -- must return None, not
    # silently accept a broken translation.
    target_code, result, tier = transpile_and_validate_hybrid(
        source, "add_pairs", test_inputs, always_wrong, always_wrong,
        primary_attempts=2, fallback_attempts=2)
    print(f"Scenario 3 (both fail): tier={tier}, target_code={target_code} (expect None, None)")
    assert tier is None and target_code is None

    # Scenario 4: no fallback configured, primary fails -- must return None cleanly,
    # not raise.
    target_code, result, tier = transpile_and_validate_hybrid(
        source, "add_pairs", test_inputs, always_wrong, fallback_translate_fn=None,
        primary_attempts=2)
    print(f"Scenario 4 (no fallback configured): tier={tier}, target_code={target_code} (expect None, None)")
    assert tier is None and target_code is None

    print("\nAll hybrid control-flow scenarios passed.")

    print("\n=== Pool-level stats over a small mixed batch ===")
    samples = [
        {"source_code": source, "func_name": "add_pairs", "test_inputs": test_inputs},
        {"source_code": source, "func_name": "add_pairs", "test_inputs": test_inputs},
        {"source_code": source, "func_name": "add_pairs", "test_inputs": test_inputs},
    ]
    # Simulate: sample 0 -> primary works, sample 1 -> needs fallback, sample 2 -> total failure.
    call_log = []
    def mixed_primary(prompt):
        call_log.append("primary")
        idx = call_log.count("primary")
        return "function add_pairs(a, b) { return a + b; }" if idx == 1 else "function add_pairs(a, b) { return a - b; }"
    def mixed_fallback(prompt):
        call_log.append("fallback")
        idx = call_log.count("fallback")
        return "function add_pairs(a, b) { return a + b; }" if idx == 1 else "function add_pairs(a, b) { return a - b; }"

    stats = hybrid_transpile_pool(samples, mixed_primary, mixed_fallback,
                                   primary_attempts=1, fallback_attempts=1)
    print(f"n_total={stats['n_total']}, primary_success={stats['n_primary_success']}, "
          f"fallback_success={stats['n_fallback_success']}, total_failure={stats['n_total_failure']}")
    print(f"fallback_invocation_rate={stats['fallback_invocation_rate']:.2f} "
          f"(cost proxy: fraction of pool that needed a paid call)")