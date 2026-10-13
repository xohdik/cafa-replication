# CAFA: Capability Attribution via Functional ANOVA
## A Factorial Framework for Decomposing Generalization in Software Engineering AI Models

**Target venue:** IEEE Transactions on Software Engineering (TSE)
**Status:** Draft research plan v0.1
**Owner:** Tcode (Tunde), UESTC

---

## 1. Motivation

SE benchmark papers report a single aggregate performance number and call it
"generalization." That number is a mixture of at least five distinct,
mechanistically different phenomena:

- **Memorization (M)** — the model has seen this exact repository/code during
  training.
- **Lexical dependence (L)** — the model keys on identifier names / surface
  tokens rather than program logic.
- **Structural pattern-matching (S)** — the model recognizes AST shape /
  control-flow templates rather than reasoning about behavior.
- **Semantic reasoning (R)** — the model reasons about program behavior in a
  way that survives translation to a different surface form entirely
  (e.g. another language).
- **Benchmark bias (B)** — exploitable statistical regularities in the
  benchmark itself, unrelated to the underlying task (label imbalance cues,
  length correlations, near-duplicate-but-not-identical samples).

Two models can score identically on a leaderboard for completely different
reasons. Current evaluation collapses all five into one number. This project
builds an instrument that doesn't.

## 2. Positioning Against Prior Work

This space is active, not empty — position explicitly rather than let a
reviewer surface these independently:

- **RepoReasoner** (I/O rewriting to strip memorization on repo-level
  reasoning) isolates **M** with one instrument, one intervention, no
  interaction analysis.
- **Cutoff-based generalization studies** (mutation + pre/post-cutoff
  comparison) isolate **M** and touch **B**, again as a single ablation.
- **Mechanistic attribution work** (attention short-circuiting to localize
  memorization by layer) isolates **M** at the architecture level, not the
  benchmark-score level.
- Your own **TOSEM** (entity-level split leakage) and **EMSE** (pair-level
  split leakage) work is itself a partial instrument for **B**.

**The gap:** no existing work estimates all five sources *simultaneously* in
one design, and none can speak to *interaction effects* between them (e.g.
"memorization and lexical dependence are usually confounded — models that
memorize also tend to have been trained on repos with consistent naming
conventions, so studies that ablate only one look like they're measuring a
bigger or smaller effect than they are"). Single-ablation studies cannot
separate that. A factorial design can.

**Citational shield structure for related work section:** one paragraph per
prior instrument, each ending with an explicit statement of what it cannot
tell you that CAFA can.

## 3. Research Questions

- **RQ1 (primary):** What are the standalone (`S_i`) and interactive
  (`S_Ti − S_i`) contributions of memorization, structure, semantics,
  benchmark bias, and lexical dependence to reported performance on SE code
  tasks?
- **RQ2:** Do these contributions differ across model families and scales?
- **RQ3:** Do they differ across SE task types (code generation vs.
  non-generative tasks — defect prediction, bug localization)?
- **RQ4 (validity, prerequisite):** Do the five perturbation operators
  function as clean, low-cross-contamination isolators of their intended
  factor?

RQ4 must be answered *before* RQ1–3 are trusted — it's the manipulation
check, not an afterthought.

## 4. Theoretical Framework

Treat the five interventions as binary switches $X_1 \ldots X_5 \in
\{-1,+1\}$:

| Switch | +1 (baseline) | −1 (perturbed) |
|---|---|---|
| $X_1$ Repo overlap | Original repo data | Deduplicated / strict temporal cutoff |
| $X_2$ Identifiers | Original names | Obfuscated / renamed |
| $X_3$ AST structure | Original layout | Randomized valid AST (independent-statement reordering) |
| $X_4$ Language | Original language | Cross-transpiled |
| $X_5$ Syntheticity | Real-world code | Counterfactual / synthetic |

Performance $Y(X_1,\ldots,X_5)$ admits a Hoeffding–Sobol / functional ANOVA
decomposition:

$$Y = f_0 + \sum_i f_i(X_i) + \sum_{i<j} f_{ij}(X_i,X_j) + \ldots + f_{1,2,3,4,5}$$

**First-order index** (standalone contribution of switch $i$):

$$S_i = \frac{\mathrm{Var}_{X_i}\left(E_{X_{\sim i}}[Y \mid X_i]\right)}{\mathrm{Var}(Y)}$$

**Total-order index** (standalone + all interactions involving $i$):

$$S_{T_i} = 1 - \frac{\mathrm{Var}_{X_{\sim i}}\left(E_{X_i}[Y \mid X_{\sim i}]\right)}{\mathrm{Var}(Y)}$$

The gap $S_{T_i} - S_i$ is the interactive variance attributable to factor
$i$ — the thing sequential ablation structurally cannot report, because
sequential subtraction assigns shared variance entirely to whichever
intervention was applied first.

**Explicit assumption to state in the paper (do not let this be implicit):**
because the design is a $2^{5-1}$ Resolution V fraction rather than a full
$2^5$, main effects and two-way interactions are estimated cleanly, but
$S_{T_i}$ as reported is really $S_i + \sum_j S_{ij}$ (main effect plus
*estimable* two-way interactions) — an approximation to the true total index
that assumes three-way-and-higher interactions are negligible. This is the
standard Design-of-Experiments assumption (Montgomery, *Design and Analysis
of Experiments*) and is defensible, but must be stated as an assumption, not
implied to be exact.

Note this decomposition is classical factorial-design ANOVA (Montgomery),
algebraically equivalent to Sobol indices for orthogonal $\pm1$-coded
designs — not Monte-Carlo Sobol sampling (Saltelli/SALib), which assumes a
cheap-to-sample simulator rather than sixteen expensive real experiments.
Say this explicitly so reviewers from either the DOE or the sensitivity-
analysis community recognize the method immediately.

## 5. Experimental Design

**$2^{5-1}$ Resolution V fractional factorial**, generator $I = X_1X_2X_3X_4X_5$
(equivalently $X_5 = X_1X_2X_3X_4$). 16 conditions instead of 32. Main
effects are unaliased with two-factor interactions; two-factor interactions
are unaliased with each other (aliased only with three-factor interactions,
assumed negligible per §4).

The 16-row design matrix and generator script are in `design_matrix.py`.

### 5.1 Prerequisite RQ A — Manipulation Check

Before running the 16-condition sweep: take ~500 held-out code samples, apply
$X_2$ (rename) and $X_3$ (shuffle) independently, and measure structural
distance (AST node-type distribution, upgrade to Zhang-Shasha / APTED tree-
edit-distance for the actual paper — `manipulation_check.py` currently ships
a coarse node-multiset proxy, flagged as v0) between original and perturbed
versions. Expected result to report in Section III: $X_2$ produces near-zero
structural distance, $X_3$ produces large structural distance. If not, the
operators need retuning before anything downstream is trustworthy.

### 5.2 Prerequisite RQ B — Per-Language Competence Baseline

For $X_4$ (cross-language), raw accuracy on the transpiled condition
conflates semantic-reasoning deficit with the model's baseline competence
gap between languages. Fix: collect a separate holdout set of simple
algorithmic snippets in both source and target language, compute
$R = \mathrm{Acc}_{\text{target}} / \mathrm{Acc}_{\text{source}}$ on that
holdout, and report

$$\Delta_{X_4} = \mathrm{Acc}_{\text{transpiled}} - R \cdot \mathrm{Acc}_{\text{original}}$$

A drop below the $R$-adjusted expectation is the genuine semantic-reasoning
deficit; a drop that tracks $R$ is just the model being weaker in that
language generally.

### 5.3 Task Battery

- **Primary:** code generation / completion (cleanest fit for all five
  operators).
- **Generality (RQ3), minimum viable:** one non-generative task — bug
  localization is the best fit (reuses infrastructure you already have from
  the pair-level leakage work; $X_4$ transpilation is harder to define
  cleanly for defect prediction's tabular-feature pipeline, so bug
  localization or clone detection is preferred over defect prediction here).
- **Stretch goal:** code summarization, as a second non-generative task, if
  time allows after the primary battery.

### 5.4 Models

- **Dense factorial sweep (open-weight, on the R740):** the P40s are Pascal
  (compute capability 6.1). **vLLM is not an option on this hardware** —
  confirmed, not a version-pinning issue: mainline vLLM's documented minimum
  is compute capability 7.0+, and a Pascal-support PR was closed unmerged
  upstream. Serving stack is **llama.cpp with GGUF-quantized models**,
  which is well-supported on Pascal — run with `GGML_CUDA_FORCE_MMQ=ON`
  (INT8/DP4A path) rather than default settings, since Pascal's FP16
  throughput without it is roughly 1/64th of FP32.
  Candidates: DeepSeek-Coder-6.7B, Llama-3.1-8B, StarCoder2-15B, in GGUF
  Q4_K_M/Q5_K_M/Q8_0 quantizations.
- **Confirmatory subset (API, frontier models):** run only the 4 extreme
  corner conditions (all +1, all −1, and two mixed corners) on 1–2 frontier
  API models, to show the pattern holds beyond open-weight/quantized scale
  without burning API budget on the full 16 conditions.

### 5.5 Compute Budget Note

Two corrections to the original draft, both confirmed against real hardware
output:
- The R740 has **two** P40s, not eight GPUs — re-scope timeline
  accordingly.
- vLLM does not run on this hardware at all (see §5.4) — the serving stack
  is llama.cpp/GGUF, which has different throughput characteristics than
  the fp16-on-modern-GPU numbers assumed in earlier drafts. Don't schedule
  the full sweep until Phase 0 (§10) reports real tok/s from the actual
  stack on this hardware.

### 5.6 New Threat to Validity — Quantization as a Confound

GGUF quantization is now a forced part of the pipeline, not a choice, which
introduces a nuisance variable the original design didn't account for:
quantization noise could plausibly interact with the memorization/structure
decomposition in ways indistinguishable from genuine effects (e.g. a
quantized model's degraded numerical precision might look like reduced
"structural reasoning" when it's actually just quantization error). Two
mitigations, not mutually exclusive:
  (a) Report results explicitly as characterizing the *quantized* model,
      not the base fp16 model — scope the claims accordingly rather than
      let a reviewer assume otherwise.
  (b) Get access to a small amount of non-Pascal compute (departmental
      cluster, cloud A100/H100 rental) for a spot-check subset — rerun a
      handful of the 16 conditions at fp16 on modern hardware and confirm
      the decomposition pattern doesn't flip. Doesn't need to be the full
      sweep, just enough to bound how much quantization is distorting
      things.

## 6. Statistical Analysis Plan

- Compute $S_i$ and the aliased-interaction-inclusive $S_{T_i}$
  approximation directly from the 16 condition means via factorial contrast
  coefficients (`analysis/sobol_anova.py`) — no Monte Carlo needed, this is
  closed-form given the design.
- 5–10 bootstrap replicates per condition (different random seeds for the
  stochastic operators — $X_3$ shuffle order, $X_5$ synthetic sample draw)
  to get confidence intervals on each $S_i$ / $S_{T_i}$.
- Report the full alias structure in an appendix table so readers can see
  exactly which three-factor interactions are being assumed negligible for
  each reported total-order index.

## 7. Engineering Plan / Perturbation Operators

Composability requirement, stated explicitly because it's easy to
underestimate: each of the 16 conditions is a **specific combination** of
all five switches applied to the *same underlying sample* (e.g. condition 13
needs a sample that is simultaneously deduplicated, renamed, shuffled, *and*
synthetic). The five operators must chain cleanly on one input — this is
the main engineering risk in the project, not the model inference.

| Operator | Status | Notes |
|---|---|---|
| $X_1$ dedup / cutoff | **Reuse** | Plug in the entity-level leakage tooling from TOSEM directly — don't rebuild. |
| $X_2$ identifier rename | **Implemented (Python)** | `perturbations/identifier_rename.py`, AST-based alpha-renaming. Multi-language needs tree-sitter; Python-only for the pilot. |
| $X_3$ AST shuffle | **Implemented (Python, v0)** | `perturbations/ast_shuffle.py`, def/use dependency analysis, permutes only mutually-independent statement blocks. Does not yet handle nested control flow finely, and has no differential-testing verification that behavior is preserved — add before trusting it at scale. |
| $X_4$ transpilation | **Stub / interface only** | Recommend LLM-based translation with test-suite-equivalence validation rather than a rule-based transpiler (better coverage across constructs); needs its own validation pass before use. |
| $X_5$ synthetic/counterfactual | **Stub / interface only** | Template-based generation matched to the real-code complexity distribution (avoid the synthetic condition being trivially easier/harder for reasons unrelated to reasoning). |
| Manipulation check | **Implemented (v0 proxy)** | `perturbations/manipulation_check.py` — coarse AST node-multiset distance. Upgrade to Zhang-Shasha/APTED tree-edit-distance before the actual paper submission. |

## 8. Deliverable

Open-source toolkit (working name **CAFA**) that takes a code sample +
5-switch configuration and returns the perturbed sample, plus a report
generator that takes a filled-in 16-condition performance table and returns
the $S_i$/$S_{T_i}$ decomposition with confidence intervals. This is the
artifact TSE reviewers want alongside the theory — something another lab can
run on their own benchmark next week.

## 9. Threats to Validity

- **Aliasing assumption** — three-way-and-higher interactions assumed
  negligible; state this explicitly, don't imply the design is exact.
- **Operator fidelity** — each perturbation must be shown (RQ4) to isolate
  what it claims to isolate; a leaky operator invalidates the corresponding
  $S_i$.
- **Language coverage** — Python-only pilot; multi-language claims need
  tree-sitter-based operators before generalizing.
- **Model coverage gap** — open-weight dense sweep vs. frontier-model
  4-corner confirmatory subset; findings on the full decomposition are only
  as strong as the open-weight sweep, frontier results are directional only.
- **Task generality** — RQ3 rests on one additional task type at minimum;
  claims of cross-task generality should be scoped to what's actually run.

## 10. Timeline (phased, assumes this runs alongside existing TOSEM/EMSE/S4N1/IRT work)

| Phase | Content | Rough scope |
|---|---|---|
| 0 — Pilot | Set up isolated `cafa` conda env (Python 3.11, separate from any shared env); confirm llama.cpp/GGUF serving works on the P40s with `GGML_CUDA_FORCE_MMQ=ON`; run RQ4 manipulation check; run full 16-condition sweep on **one** model family, **one** task (code generation) | Smallest thing that validates the whole pipeline end to end |
| 1 — Primary sweep | Extend to 2–3 model families, code generation task, compute $S_i$/$S_{T_i}$ with bootstrap CIs | Core RQ1/RQ2 results |
| 2 — Generality | Add bug localization task battery for RQ3 | |
| 3 — Frontier confirmatory | 4-corner subset on 1–2 API models | |
| 4 — Writing | Related work (citational shield), results, toolkit release, submission | |

## 11. Fit for TSE

Theory-driven (introduces a measurement framework, not an algorithm),
methodological (reusable toolkit, not a one-off finding), and general
(applies across code generation, defect prediction, bug localization,
summarization — anywhere a benchmark reports a single accuracy number).
Explicitly *not* competing with the TOSEM/EMSE leakage papers — those become
motivating prior instances cited in §2, not results this paper repeats.
