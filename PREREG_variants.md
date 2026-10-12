# Pre-registration: generator variants and the answer-8 demonstration for three more models (CAFA, Part 2B)

Status: written before any run below. Commit this file, `make_variants.py`, `variants_analysis.py`, `demo8.py`
and `run_part2b.sh` first; record the commit hash and date in the paper's Data Availability paragraph.

Date fixed: [YYYY-MM-DD]    Commit: [hash]

## What the manifest shows (observed before this plan)
All 1,541 generator programs are scored on the same stdin, the first of the manifest's stdin cases, "3\n1 2 3\n" (n = 3; the
second line is never read). Each program starts `n = int(input())`, ends its loop body with dead assignments `_pad0 = v`,
`_pad1 = v`, ..., and the number of pads varies from a few to several dozen (the generator pads to match line counts).

## Question
DeepSeek-Coder answers 10 on about half of the generator programs even when the demonstration's answer is 8 or absent.
Is that preference tied to the fixed input value, to the padding lines, or to neither?

## Variants (condition 2 only, original names, original prompt, 1,541 programs; DeepSeek-Coder-6.7B and StarCoder2-7B, Q4_K_M)
| Variant | Change | Verification |
|---|---|---|
| n5 | the stdin is "5\n1 2 3 4 5\n" instead of "3\n1 2 3\n" | the program must run on the new stdin; the expected output is recomputed by execution |
| nopad | every line `_padK = V` is deleted (`pass` inserted where a block would be empty) | the changed program must run and print the same output as the original on the original stdin |
Programs failing verification are left out and counted (`variants_report.json`). Both changes alter something the matched generator
was built to keep (n5: the true outputs; nopad: line count, which drops by about half), so a change in accuracy is not by itself
a change in the model's preference; the first-line statistics below are the primary outcome.

## Outcomes (paired by program, bootstrap 10,000 resamples, seed 20261012)
1. Share of programs whose first output line is 10, base against variant (paired difference with 95% interval).
2. Penalty (accuracy on generator programs minus accuracy on the real programs, unchanged), base against variant.
3. The five most common first lines, and the share of programs whose CORRECT first line is 10 (so that a prior is not
   confused with a true answer).

## Reading rules, fixed in advance
- The preference for 10 "weakens" if the share of first lines equal to 10 falls by at least 10 points and the 95% interval excludes 0.
- The penalty "shrinks" if it moves toward 0 by at least 3 points and the 95% interval excludes 0.
| Variant | Result | Reading reported in the paper |
|---|---|---|
| n5 | preference weakens or moves | the preference is tied to the input value; report which first lines the model now favours |
| n5 | does not weaken | the input value is not the source |
| nopad | preference weakens and penalty shrinks | padding lines drive part of the penalty: a property of this generator, not of syntheticity as such |
| nopad | weakens but penalty does not shrink, or the reverse | mixed; reported as such |
| nopad | neither | the remaining candidates are program form and naming; say so |
Results are reported for each model separately; no pooling across models.

## Answer-8 demonstration for CodeLlama-7B, Qwen2.5-Coder-7B and Qwen2.5-Coder-14B
Same design as for DeepSeek-Coder and StarCoder2 (conditions 1, 2, 5, 6; original prompt with input 4 and answer 8). Reported
descriptively with the same statistics (`demo8.py`): first-line shares of 10 and 8, the penalty and the interaction under both
demonstrations and their differences. No new decision rule; the paper's statement that anchoring on the answer explains a small
part of the penalty is extended to a model only if its penalty with the answer-8 demonstration is within the interval of the
original one.

## Procedure
1. `python3 make_variants.py` (from `capa/`, `cafa` env); check `variants_report.json` (failures should be few).
2. Commit this file and the scripts; record hash and date above.
3. `nohup bash run_part2b.sh > /dev/null 2>&1 &` (two GPUs).
4. `python3 variants_analysis.py rerun_ds_q4.jsonl rerun_dsvar_n5_q4.jsonl | tee var_ds_n5_out.txt` and the three further pairs
   (ds/nopad, sc2/n5, sc2/nopad; base files `rerun_ds_q4.jsonl`, `rerun_sc2_q4.jsonl`).
5. `python3 demo8.py rerun_cl_q4.jsonl rerun_clorig8_q4.jsonl | tee demo8_cl_out.txt`, and the same for `q7` and `q14`.
Deviations are logged in `DEVIATIONS.md`.
