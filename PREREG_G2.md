# Pre-registration: a second generator (G2) for CAFA

Status: written before G2 programs were generated and before any model was scored on them. Commit this file,
`g2_features.py`, `g2_generate.py` and `g2_balance.py` first; record the commit hash and date in the paper's Data
Availability paragraph and fill the bracketed fields.

Date fixed: 2026-10-16    Commit: 56d3ef696c2c0dd3bc6617718442c9887f455672
Script hashes (sha256 prefix, recompute if a file changes before the commit): g2_features.py e0e14d2b1cda,
g2_generate.py 2f1e3bdb7c5f, g2_balance.py c88e391b9579.

## Question
Every generator result in the paper is a result about one generator (G1). G1 held several things fixed: one stdin (3, then 1 2 3),
dead assignments added to reach a line target, outputs that are small constants, one naming vocabulary and one construction
method. Do the generator-dependent findings (the generator effect at original names, the identifiers x source interaction,
the prompt dependence of both, and the reordering of 15 models) reproduce with a generator built differently?

What a positive answer is worth: two generators show the findings are not specific to G1's conventions. They do not isolate
"syntheticity" as such, because both generators share the authors' notion of what a program looks like, and the paper will say so.
G2 is independent in construction (separate code, templates, input and output model, naming rule, no padding), not in authorship.

## What G2 is (see the header of `g2_generate.py`)
It reads only the real program of each sample and builds one program per sample, matched on: non-blank lines, cyclomatic
complexity, nesting depth, output shape (0 / 1 / several lines), stdin lines and tokens, digit length of input integers,
mean identifier length and share of one-letter identifiers. It differs from G1 on purpose:
- input: a fresh random stdin per sample with the real input's shape and magnitude (values not copied), plus two further cases;
- output: computed from the input by live code (it must change when the input changes, except in the zero-output shape);
- padding: none; every assigned name is read later (AST def-use check);
- templates: a separate statement grammar (readers, accumulators, filters, pair loops, string and word operations, helper functions, nested blocks);
- naming: three vocabularies (terse, mixed, descriptive) mixed to match the real program's identifier statistics.
Fixed parameters: seed 20261014, `--p-indep 0.6` (probability that an operand is an input variable rather than a derived one;
it controls how many statements are independent and therefore reorderable), `--max-attempts 400`, tolerance levels 0 and 1 as in the script.
The statement order of G2 programs is NOT tuned to the AST shuffle: the share of G2 programs that the shuffle changes is a
measured outcome (reported, compared with 35% of real and 9% of G1 programs), not a target.

## Revision before registration (logged; no model output has been seen)
A first generation (generator v1, hashes 99ba36fd758b, ffc6344691d4, 47994d20d83d) was run on the confirmation manifest to test the
pipeline. It matched 1,355 of 1,542 samples (87.9%, below Gate A) and left the stdin size covariates unbalanced (SMD -0.40 for lines,
-0.31 for tokens), because v1 capped real inputs at 4 lines and 8 tokens per line, the single-letter name vocabulary ran out for programs
with many one-letter names, and 24 real programs failed under v1's resource limits (3 s, 1 GB) although they ran in the paper's harness.
Generator v2 (the hashes above) reproduces tables of rows and count headers (caps: 24 tokens per line, 30 rows, 60 tokens in all, 9 digits),
falls back to any free letter for one-letter names, runs real programs under generous limits (20 s, 16 GB), and adds forms that
update an existing accumulator, library calls (math, collections) and Yes/No outputs, so that unmatched samples are not simply the
longer or more import-heavy programs. Gate thresholds are unchanged except that the stdin size covariates are compared on the log
scale (log of 1 + count), because real input sizes are heavy-tailed and a capped generator cannot match the tail. The v1 outputs are
kept as `g2_base_v1.json` and `g2_report_v1.json`. A further revision of the generator after seeing v2's gates is allowed at most
twice more, only on programs and covariates, and is logged in `DEVIATIONS.md`.


Second and third generators (v3, then v3b; all before registration and before any model output). Generator v2 (520306380887) was run on the confirmation
manifest and failed both gates. Gate A: 1,392 of 1,542 samples matched (90.3%); the 150 unmatched are long, deeply nested real programs (real depth 5.97
against 2.56 for the matched; 143 have depth 4 or more) that the v2 forms could not reach (depth above 5). Gate B: cc +0.101, name_len_mean -0.256 and
name_single_frac +0.178 failed; lines, depth, both stdin sizes and output shape passed.
Generator v3 (g2_generate.py 21ec3e1dce56) adds depth steering: after the statements are chosen, a suffix of the program body is wrapped in an always-true
guard on an input variable (five spellings, never repeated), a try/except, or a short loop (at most two) until the depth reaches the target, with lines and
cc for the guards reserved in advance. It was run on the confirmation manifest: Gate A passed (1,522 of 1,542, 98.7%), depth SMD +0.000, cc +0.095,
but name_len_mean (-0.229) and name_single_frac (+0.186) still failed Gate B. A synthetic-target test traced this to the first program accepted inside
the tolerance running 0.3 to 0.6 short on mean name length and about one point high on cc.
Generator v3b (g2_generate.py 2f1e3bdb7c5f) keeps v3 and adds (1) a naming mixture aimed 0.6 above the target mean name length, with the all-terse branch starting
at a single-letter share of 0.9 instead of 0.8, and (2) selection of the closest of up to four acceptable programs per sample (sum of the distances to the
lines, cc, name length and single-letter targets in units of their tolerances) instead of the first. Gate thresholds, tolerances, matched covariates and
the check that output depends on input are unchanged. Of the two further revisions allowed after v2, v3 was the first and v3b is the second; none remains,
so if v3b fails Gate B, G2 is reported as not balanced under the rule above.

## Gates, checked before any model is run
All gates use only programs and covariates, never model output.
- Gate A, coverage: at least 95% of the 1,542 samples receive a G2 program at tolerance level 0 or 1. Unmatched samples are listed
  with their covariates, and the paired analyses are repeated without them (selection check). Difficult samples are not dropped silently.
- Gate B, balance (`g2_balance.py`, printed as a table): |SMD| < 0.10 for each matched covariate (lines, cc, name_len_mean,
  name_single_frac, log stdin lines, log stdin tokens, out_shape), and < 0.15 for depth. If a gate fails, only generator parameters (tolerance, attempts, seed) may change;
  at most three regenerations, each logged in `DEVIATIONS.md`. If it still fails, G2 is reported as not balanced and the study
  stops at this gate (a result in itself).
- Gate C, execution: every G2 program and every obfuscated and shuffled variant runs on all three stdin cases within the time
  limit, and the four generator conditions print identical output (the audit of `audit_final.py`, extended to G2).
- Reported, not gated: classifier AUC for real versus G1 and real versus G2 (covariates, covariates not matched, character
  n-grams), the free-covariate table, the share of G2 programs equal to G1's, and the shuffle change rate.
The G2 manifest hash is recorded in the paper once the gates pass.

## Experiments (only after the gates)
- E1, main replication: five base models (Q4_K_M), conditions 2, 4, 6, 8 built from the G2 programs, original prompt. Conditions
  1, 3, 5, 7 are the confirmation run's (same real programs). 4 x 1,542 x 5 = 30,840 generations. Analysis: the eight-condition
  estimators of the paper (seven terms per model, 10,000 program-level resamples, seed 20261012, Holm within model).
- E2, prompt: G2 conditions 2 and 6 with no demonstration, five models: 2 x 1,542 x 5 = 15,420. With the existing no-demonstration
  reruns of conditions 1 and 5, this gives the 2 x 2 x 2 (identifiers x source x prompt, statement order original) per model.
- E3, ranking: ten further models, G2 condition 2 (original names) under the original and the no-demonstration prompt:
  10 x 2 x 1,542 = 30,840. The five main models come from E1 and E2. Same statistics and noise ceiling as `PREREG_ranking.md`.
Total about 77,100 generations. Decoding, prompt, scoring and quantization unchanged from the paper.

## Hypotheses and decision rules, fixed in advance
Estimands are those of the paper: the program-source main effect (averaged over identifiers and statement order), its simple effect
at original names, and the identifiers x source interaction, per model.
- H1, direction replicates (DeepSeek-Coder and StarCoder2, the two models with large G1 interactions): the identifiers x source
  term under G2 is positive with Holm-adjusted p < 0.05. Replicated if both models satisfy it; partly if one; not if neither.
- H2, generator dependence (all five models): paired by sample, the difference G2 minus G1 in (a) the source effect at original
  names and (b) the identifiers x source term, with a program-level bootstrap interval. A quantity is called generator-dependent
  for a model if the difference is at least 3 points and its Holm-adjusted p < 0.05 (Holm over 5 models x 2 quantities). Quantities
  that are not called generator-dependent are reported with their intervals and are not called equal.
- H3, prompt dependence: the source x prompt term has the same sign under G2 and G1 in at least 4 of 5 models, each with Holm
  p < 0.05 under G2.
- H4, ranking: instability replicates if the real-versus-G2 Kendall tau-b is below the 5th percentile of the split-half noise ceiling
  under both prompts. It depends on the prompt if only one; it does not replicate if neither. Also reported: the share of
  discordant pairs for G2, and the agreement of the G1 and G2 orderings of the 15 models (tau-b).
Reading in the paper (chosen now): H1 and H3 hold and H2 finds little -> "not an artifact of G1's conventions" for the
interaction; H1 fails -> the interaction is reported as a property of G1; H2 generator-dependent for a model -> that model's
source effect is described as depending on the generator; H4 not replicated -> the ranking claim is withdrawn and the five-model
statement is reported as generator-specific. No result is reworded after it is seen. Results are reported per model; no pooling.

## Not claimed, whatever the result
G2 does not show that models recognise generated code, does not isolate syntheticity, and does not address memorization, which the
real-versus-generator contrast still confounds with source. A third, differently authored generator (for example one written by
a language model not among the evaluated models) is future work.

## Procedure
See `RUN_G2.md`. Deviations are logged in `DEVIATIONS.md`.
