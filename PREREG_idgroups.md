# Pre-registration: which identifiers carry the naming effect, on the 1,541-program confirmation set (CAFA, Part 2C)

Status: written before any run below. Commit this file and `run_idgroups.sh` first (`name_ablation.py` and
`name_ablation_readable.py` are already in the repository, unchanged since the pilot); record the commit hash and date in the paper's
Data Availability paragraph.

Date fixed: 2026-10-13    Commit: [hash]

## Background (observed before this plan)
On the pilot sample the identifier-group checks gave, for DeepSeek-Coder-6.7B (condition 2 with one group renamed, change in accuracy
against the unrenamed program, same programs): `n` only +10.2 points [+7.3, +13.3]; `result` only +12.0 [+9.0, +15.1]; every identifier
(reproduces condition 6) +11.0 [+7.3, +14.8]; loop variables +1.7 [0.0, +3.3]; dead `_pad` variables -2.8 [-5.0, -0.9]. Readable renames
(`n` to `count`, `result` to `total`) +0.2 [-1.7, +2.1] and +1.1 [-0.6, +2.8], both +0.9 [-1.3, +3.0]. For Qwen2.5-Coder-7B renaming
everything cost -4.4 [-6.7, -2.1] and no single group reproduced it. These checks were never run on the confirmation set.

## Question
Do the pilot findings replicate on the 1,541 confirmation programs, which the pilot did not use?

## Design
Same scripts, same prompt, same harness (greedy, 64 new tokens, n_ctx 8192) as in the pilot, run on `manifest_confirm.json`.
Condition 2 (generator program, original names) is the base; one group of identifiers is renamed with the names that the identifier
obfuscation of condition 6 assigns (`name_ablation.py`: none, n, result, loop, pad, other, all) or with readable names
(`name_ablation_readable.py`: none, n to count, result to total, both). A renamed program must run and print the same output as the
original on the scoring input, otherwise it is dropped and counted. Models: DeepSeek-Coder-6.7B and Qwen2.5-Coder-7B, Q4_K_M, the two
models of the pilot. Changes are paired by program and the intervals are 95% bootstrap intervals over programs
(10,000 resamples, seed 0 as in the scripts). Nothing else is varied.

## Reading rules, fixed in advance
DeepSeek-Coder-6.7B. Let D(all) be the change for renaming every identifier.
1. The effect "replicates" if D(all) > 0 with an interval excluding 0.
2. A group "carries" the effect if its interval excludes 0 on the positive side and its point estimate is at least half of D(all).
3. Replication of the pilot pattern requires that `n` and `result` each carry the effect and that `loop` and `pad` do not.
4. The readable renames are "not specific to the tokens" if the change for `both` has an interval that includes 0 or an upper bound
   below half of D(all); otherwise the pilot statement that readable renames do not help is withdrawn.
Qwen2.5-Coder-7B.
5. The cost replicates if D(all) < 0 with an interval excluding 0. A group "reproduces" it if its interval excludes 0 on the negative
   side and its point estimate is at least half of D(all); if no group does, the cost is reported as spread across groups.
Outcomes that match none of these are reported as they are and described as mixed. Results are reported per model and per group,
with the number of programs having the group and the number dropped; no pooling across models. The paper's Appendix B and Threats are
updated to say whether the pilot statements stand on the confirmation set; if rule 3 fails the sentence on `n` and `result` is removed.

## Procedure
1. Commit this file and `run_idgroups.sh`; record hash and date above.
2. `nohup bash run_idgroups.sh > /dev/null 2>&1 &` (two GPUs: DeepSeek-Coder on GPU 0, Qwen2.5-Coder-7B on GPU 1).
3. Outputs: `ablate_conf_{ds,q7}.json`, `readable_conf_{ds,q7}.json` and the printed tables `idgroups_{ds,q7}_out.txt`.
   The pilot outputs (`ablate_*.json`, `readable_*.json`) are not touched.
Deviations are logged in `DEVIATIONS.md`.
