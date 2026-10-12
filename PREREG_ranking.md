# Pre-registration: do generator programs reorder code models? (CAFA ranking study)

Status: written before any of the new models below was scored. Commit this file, `rank_models.json` and
`rank_analysis.py` first; record the commit hash and date in the paper's Data Availability paragraph.
Fill the bracketed fields before committing.

Date fixed: [YYYY-MM-DD]    Commit: [hash]

## Question
The paper reports that the order of five models differs between real CodeNet programs and matched generator programs.
With five models that is a statement about ten pairs. This study asks how large the reordering is across 15 models.

## Data and models
- Programs: the 1,541 confirmation programs of `manifest_confirm.json` (one per problem), condition 1 (real, original
  names) and condition 2 (generator, original names). No other conditions are scored.
- Prompts: the original one-shot prompt (`orig`) and the same prompt with no demonstration (`none`), both as in the paper.
- Decoding and scoring: unchanged from the paper (greedy, 64 new tokens, exact match after normalization). All models Q4_K_M.
- Models (base checkpoints only; confirm each on its model card before committing):

| Model | Params (B) | Source repo and file | Base checkpoint confirmed |
|---|---|---|---|
| DeepSeek-Coder-6.7B, StarCoder2-7B, CodeLlama-7B, Qwen2.5-Coder-7B, Qwen2.5-Coder-14B | 6.7 to 14 | already scored in the paper (reruns, conditions 1 and 2) | yes |
| DeepSeek-Coder-1.3B | 1.3 | `TheBloke/deepseek-coder-1.3b-base-GGUF`, `deepseek-coder-1.3b-base.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| Qwen2.5-Coder-1.5B | 1.5 | `mradermacher/Qwen2.5-Coder-1.5B-GGUF`, `Qwen2.5-Coder-1.5B.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| Qwen2.5-Coder-3B | 3 | `mradermacher/Qwen2.5-Coder-3B-GGUF`, `Qwen2.5-Coder-3B.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| StarCoder2-3B | 3 | `second-state/StarCoder2-3B-GGUF`, `starcoder2-3b-Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| StarCoder2-15B | 15 | `second-state/StarCoder2-15B-GGUF`, `starcoder2-15b-Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| CodeLlama-13B | 13 | `TheBloke/CodeLlama-13B-GGUF`, `codellama-13b.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| CodeGemma-7B | 7 | `mradermacher/codegemma-7b-GGUF`, `codegemma-7b.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| Granite-Code-3B-128k | 3 | `mradermacher/granite-3b-code-base-128k-GGUF`, `granite-3b-code-base-128k.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| Granite-Code-8B-128k | 8 | `mradermacher/granite-8b-code-base-128k-GGUF`, `granite-8b-code-base-128k.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |
| Yi-Coder-9B | 9 | `mradermacher/Yi-Coder-9B-GGUF`, `Yi-Coder-9B.Q4_K_M.gguf` | upstream model on the repo page is the base checkpoint; confirm on its model card: [yes/no] |

Choices made when the list was fixed: the Granite 128k variants are used because the study's window is 8,192 tokens and the 2k and 4k variants are shorter; where several repos offered a file, a static (non-imatrix) Q4_K_M quant was preferred, as for the five existing models.

Reserve models, used only to replace a listed model that fails to load or fails the smoke test, in this order:
Qwen2.5-Coder-0.5B, CodeGemma-2B. No model is added or dropped after results are seen. A model is excluded only if
llama.cpp cannot load it or the smoke test (20 programs) returns no scored cells; every exclusion is reported.
The five existing models were scored before this document was written; the ten new ones are not.

## Outcomes (per prompt)
1. Kendall's tau-b between the 15 accuracies on real programs and the 15 accuracies on generator programs.
2. The share of model pairs (105 pairs) whose order differs between the two sets of programs, and the same share among
   pairs whose order on real programs is itself resolved (bootstrap interval of the accuracy difference excludes 0).
3. A table of accuracy and rank on each kind of program, and a chart of real-program rank against generator-program rank.

## Uncertainty and the threshold
- Program-level bootstrap, 10,000 resamples, the same resampled programs for real and generator accuracies, seed 20261012;
  95% percentile intervals for tau and for the flip share. Only programs scored for every model in both conditions are used.
- Noise ceiling: 1,000 random splits of the programs into two disjoint halves; tau between the rankings on the two halves
  of the REAL programs. A reordering is called material if tau (real against generator, all programs) is below the 5th
  percentile of that split-half distribution. The split-half ceiling is conservative: half-size samples are noisier than
  the full sample, so the ceiling is lower and a material reordering is harder to claim.

## Decision rules, fixed in advance
- Generator programs reorder models (claim stated in the paper): material under both prompts.
- Reordering depends on the prompt: material under exactly one prompt. The paper then says so.
- No reordering beyond noise: material under neither prompt; the paper's five-model statement is then reported as
  not replicated at 15 models.
- Sensitivity analysis (reported in addition, not instead): the same statistics after dropping models with accuracy below
  5% on both kinds of programs (floor effects).

## Procedure
1. `python3 gguf_tool.py find "<model name> GGUF"`, check the model card, `python3 gguf_tool.py get <repo> <file>`.
2. Replace the FILL entries in `rank_models.json`; run `python3 make_rank_queue.py rank_models.json`.
3. `bash smoke_rank.sh` (20 programs x 2 conditions per model); inspect the printed predictions.
4. Commit this file, `rank_models.json`, `rank_analysis.py`, `make_rank_queue.py`. Record the hash and date above.
5. `nohup bash run_rank.sh > rank_out/run.log 2>&1 &` (two GPUs, resumable).
6. `python3 rank_analysis.py rank_models.json --out rank_out` and send `rank_out/rank_summary.json` and the CSV tables.
Deviations from this plan are logged in `rank_out/DEVIATIONS.md`.
