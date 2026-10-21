# PREREG_R4 -- multi-input scoring of real programs (Revision 4)

Frozen before any model is run on the extra inputs. Inputs: `r4_inputs.json` (committed; generator `r4_build_inputs.py`, second version, revised once after a coverage diagnostic and before any model saw an input: `r4_report_v1.md`, `r4_report.md`).

## Question
The paper scores each program on one input (the CodeNet sample). Does the effect of identifier obfuscation on real programs (condition 5 versus condition 1), and the accuracy level itself, depend on that single input?

## Design
Five main models (DeepSeek-Coder-6.7B, StarCoder2-7B, CodeLlama-7B, Qwen2.5-Coder-7B, Qwen2.5-Coder-14B), Q4_K_M, original prompt, conditions 1 and 5, greedy decoding, the harness of the paper. Each program is scored on its official input (already scored) and on every accepted extra input (one or two). Programs with at least one accepted extra input form the analysis set; a program enters a model's analysis only if all of its cells for conditions 1 and 5 are scored. The number of programs dropped for missing cells is reported.

## Quantities (per program, in points x100 when averaged)
- single: correct on the official input (the paper's measure).
- mean: fraction of its inputs (official plus extras) on which the model is correct. This is the primary measure.
- strict: correct on every input.
- I|real = condition 5 minus condition 1, computed for each of the three measures on the same programs.
- difference = I|real(mean) - I|real(single).
- inflation = accuracy(single) - accuracy(strict) for condition 1; and the share of programs correct on the official input but not on all inputs.
Program-level bootstrap, 10,000 resamples, seed 20261012, unadjusted 95% percentile intervals; Holm correction over the five models for I|real(mean).

## Decision rules and the sentence we will write
- Direction: I|real(mean) is negative in all five models. Size: |difference| <= 1.5 points in every model.
  - Both hold -> "the identifier effect on real code does not depend on the single-input oracle."
  - Direction holds, size does not -> "the sign holds; we report the multi-input estimate as the estimate."
  - Direction fails in a model -> "for that model the identifier effect on real code is reported as input-dependent."
- Inflation is descriptive: it is reported, with no threshold, as the amount by which single-input accuracy overstates program-level accuracy.

## Not claimed
Only conditions 1 and 5 are rescored. The AST-shuffle conditions, G1 and G2 are not rescored on the extra inputs; their output equivalence on the extra inputs is checked in `r4_report.md` (no failures). Extra inputs are produced by redrawing the official input and are accepted by agreement with other CodeNet submissions that reproduce the official output; they are not a test suite written by the problem setters.
