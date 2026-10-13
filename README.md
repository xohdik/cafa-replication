# CAFA: Controlled Attribution by Factorial Analysis

Replication package for *Controlled Attribution by Factorial Analysis (CAFA): Execution-Verified Perturbations of Identifiers,
Statement Order and Program Source in Code-Model Evaluation* (Babatunde, Wang, Chen, Wang; submitted to ACM TOSEM).

CAFA scores a code model on the same programs under every combination of three execution-verified interventions, a full 2^3
factorial, and reports signed effects with program-level bootstrap intervals:

| Factor | Intervention | Level -1 | Level +1 |
|---|---|---|---|
| I | identifiers | original names | AST alpha-renaming to obfuscated names |
| A | statement order | original | AST shuffle of independent statements |
| S | program source | real CodeNet program | matched generator program |

Condition ids follow `cid - 1 = 4*I + 2*A + S` (C1 = real, original names, original order ... C8 = generator, obfuscated, shuffled).
The task is output prediction on Project CodeNet Python programs, scored by exact match after whitespace normalisation (greedy decoding,
64 new tokens, 8,192-token context). The confirmation set has 1,541 programs, one per problem and disjoint from the pilot at the problem
level; five base models are scored on it (DeepSeek-Coder-6.7B, Qwen2.5-Coder-7B and -14B, CodeLlama-7B, StarCoder2-7B), and ten further
base models in the pre-registered ranking study.

## What is in the repository

The layout is flat on purpose: the scripts import one another and read their inputs from the working directory, so run everything from
the repository root. The files fall into five groups.

| Group | Files |
|---|---|
| Design and construction | `design_matrix.py`, `orchestrator.py`, `identifier_rename.py` (I), `ast_shuffle.py` (A), `synthesize.py`, `synthesize_shape.py` (S), `make_confirmation_pairs.py`, `join_codenet_tests.py`, `join_codenet_dates.py`, `convert_emse_to_rq4.py`, `audit_manifest.py`, `check_synth_pairing*.py`, `verify_x*_pool.py` |
| Scoring | `scoring_harness.py` (main harness), `cafa_revision.py` (reruns that save prediction text, wrong-answer taxonomy, Q8 check), `no_program_control.py`, `complete_case.py`, `convert_checkpoint.py`, `relabel_ids.py` |
| Analysis | `paired_effects.py`, `interaction_effects.py`, `cell_means.py`, `cafa_shares.py`, `sobol_anova.py`, `compare_models.py`, `ast_subset_effects.py`, `format_confound.py`, `output_strata.py`, `matched_output_effect.py`, `selftest_listing1.py` |
| Pre-registered follow-ups | `PREREG_*.md`, `make_variants.py`, `variants_analysis.py`, `demo8.py`, `rank_models.json`, `make_rank_queue.py`, `rank_analysis.py`, `gguf_tool.py`, `fetch_rank_models.sh`, `name_ablation*.py`, `run_*.sh` |
| Development history | `x1_cutoff.py`, `transpile.py`, `stubs.py`, `measure_x4_feasibility.py`, `diagnose_*.py`, `patch_*.py`, `demo3.py`-`demo7.py`, `RESEARCH_PLAN.md`: kept for the record (two candidate factors were measured and withdrawn before the design was fixed; the paper's design section tells the story); not needed to reproduce a result |

Data and outputs sit next to the scripts: `manifest_*.json` (the built conditions), `responses_*.json` and `rerun_*.jsonl` (per-cell model
outputs, the latter with the predicted text), `npc_*.json` (no-program control), `rank_out/` (ranking study), `five/` (complete-case
files of the five-model confirmation) and the printed tables `*_out.txt`.

## Environment

Tested with Python 3.11.15, `llama-cpp-python` 0.3.34 built with CUDA support (it links the CUDA 11 runtime), `numpy` 1.26.4, on a
server with two Tesla P40 GPUs (23 GB each, compute capability 6.1), 80 CPU threads and 125 GB RAM. `environment.yml` pins the packages.
All models are served as Q4_K_M GGUF files through llama.cpp, one model per GPU. A full eight-condition sweep of one 7B model on the
confirmation set takes a few hours on one P40. The analysis scripts need only `numpy` and run on any machine.

```
conda env create -f environment.yml && conda activate cafa
```

## Models

`MODEL_SHA256.txt` lists the SHA-256 of every GGUF file used; the files are not redistributed (see each model's licence). The ten models
of the ranking study are fetched by `fetch_rank_models.sh` (repository and file names in `rank_models.json`). The five models of the
main study:

| Model | Hugging Face repository | File |
|---|---|---|
| DeepSeek-Coder-6.7B base | `TheBloke/deepseek-coder-6.7B-base-GGUF` | `deepseek-coder-6.7b-base.Q4_K_M.gguf` |
| Qwen2.5-Coder-7B | `QuantFactory/Qwen2.5-Coder-7B-GGUF` | `Qwen2.5-Coder-7B.Q4_K_M.gguf` |
| Qwen2.5-Coder-14B | `QuantFactory/Qwen2.5-Coder-14B-GGUF` | `Qwen2.5-Coder-14B.Q4_K_M.gguf` |
| CodeLlama-7B | `TheBloke/CodeLlama-7B-GGUF` | `codellama-7b.Q4_K_M.gguf` |
| StarCoder2-7B | `second-state/StarCoder2-7B-GGUF` | `starcoder2-7b-Q4_K_M.gguf` |

Each file was matched to its repository by SHA-256 (`MODEL_SHA256.txt` against the repository's file listing). Put the files in `models/` (git-ignored). The Q8_0 file used for the precision check is `deepseek-coder-6.7b-base.Q8_0.gguf` from
`TheBloke/deepseek-coder-6.7B-base-GGUF`.

## Data

The programs come from Project CodeNet (IBM). The CodeNet code repository is Apache-2.0; the dataset is released under a permissive
data licence (CDLA-Permissive-2.0 to our knowledge; check the licence shipped with your download). The manifests contain the CodeNet-derived Python source
of the 1,541 confirmation programs and of the pilot programs, their test inputs and the generator programs built from them; no
other CodeNet content is redistributed. The manifests are identified by SHA-256: the confirmation manifest
`manifest_confirm.json` is `a8978b7ad107505658e426926e3568345af18f13ebf7ede74adce45edf155c3d` and the corrected pilot manifest
`manifest_v2.json` is `cfbcac4f988b5ceff0505cabcebd7983942887800fc6bfcbd0e2e0b5b4d2263e`. Check with `sha256sum`.

## Reproducing the results

**Level 1, tables from stored outputs (minutes, CPU only).** The per-cell outputs are included, so every table can be recomputed
without a GPU. Example for the five-model confirmation (complete-case files are in `five/`):

```
S="five/responses_deepseek_confirm_cc.json:DeepSeek five/responses_qwen_confirm_cc.json:Qwen five/responses_qwen14b_confirm_cc.json:Qwen14B five/responses_codellama_confirm_cc.json:CodeLlama five/responses_starcoder2_confirm_cc.json:StarCoder2"
python3 interaction_effects.py $S          # seven signed terms, Holm-adjusted, program-level bootstrap
python3 cell_means.py $S                   # the eight condition means and the simple effects
python3 ast_subset_effects.py --manifest manifest_confirm.json $S
python3 matched_output_effect.py --manifest manifest_confirm.json $S
python3 cafa_shares.py $S                  # functional-ANOVA (Sobol) shares
python3 cafa_revision.py checks            # complete-case audit, strata, popularity, problem-count audit
python3 selftest_listing1.py               # estimator self-test (Listing 2 of the paper)
python3 rank_analysis.py rank_models.json --out rank_out     # ranking study (Kendall tau, flips, noise ceiling)
python3 demo8.py rerun_q7_q4.jsonl rerun_q7orig8_q4.jsonl    # answer-8 demonstration, one model
python3 variants_analysis.py rerun_ds_q4.jsonl rerun_dsvar_n5_q4.jsonl   # generator variants
```

**Level 2, rescoring from the manifest (GPU, hours).** Scoring needs only `manifest_confirm.json` and a GGUF file:

```
CUDA_VISIBLE_DEVICES=0 python3 scoring_harness.py --manifest manifest_confirm.json \
    --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf --reps 1 --temperature 0 \
    --out responses_deepseek_confirm.json --resume --checkpoint-every 200
python3 no_program_control.py --manifest manifest_confirm.json --gguf ./models/deepseek-coder-6.7b-base.Q4_K_M.gguf \
    --out npc_deepseek_confirm.json --resume
python3 complete_case.py responses_deepseek_confirm.json    # writes responses_deepseek_confirm_cc.json
CUDA_VISIBLE_DEVICES=0 python3 cafa_revision.py rerun --gguf models/deepseek-coder-6.7b-base.Q4_K_M.gguf \
    --conditions 1,2,5,6 --out rerun_ds_q4.jsonl                        # saves the predicted text
```

The pre-registered runs have their own scripts: `run_part2b.sh` (generator variants, answer-8), `run_rank.sh` (ranking study,
generated by `make_rank_queue.py`), `run_idgroups.sh` (identifier groups on the confirmation set).

**Level 3, rebuilding the manifest from CodeNet.** This needs the Project CodeNet release and the pairs file of the earlier
EMSE corpus (`pairs_codenet_python.json`, not included; `pairs_confirm.json`, the output of the first step, is included):

```
python3 make_confirmation_pairs.py --pairs PATH/TO/pairs_codenet_python.json --codenet PATH/TO/Project_CodeNet \
    --exclude $(ls rq4_samples*.jsonl) --out pairs_confirm.json --seed 1
python3 join_codenet_tests.py --pairs pairs_confirm.json --codenet PATH/TO/Project_CodeNet \
    --output rq4_confirm.jsonl --n 2300 --seed 1 --require-tests
python3 orchestrator.py --samples rq4_confirm.jsonl --manifest-out manifest_confirm.json --seed 0 --shape-match --normalize-baseline
python3 check_synth_pairing_ast.py manifest_confirm.json --shape && python3 audit_manifest.py --manifest manifest_confirm.json
sha256sum manifest_confirm.json
```

## From the paper to the files

| Paper | Script | Output in the repository |
|---|---|---|
| Effects of I, A, S and their interactions, five models | `interaction_effects.py` | `interaction_confirm_out.txt` (two models), `interaction_five_out.txt` (five) |
| Condition means and simple effects | `cell_means.py` | `cell_means_confirm_out.txt`, `cell_means_five_out.txt` |
| Variance shares (Sobol / functional ANOVA) | `cafa_shares.py`, `sobol_anova.py` | printed |
| Estimator self-test (Listing) | `selftest_listing1.py` | printed |
| AST shuffle on changed programs; reformatting check | `ast_subset_effects.py`, `format_confound.py` | `ast_subset_*_out.txt`, `format_confound_out.txt` |
| Output-shape strata | `output_strata.py`, `matched_output_effect.py` | `output_strata_out.txt`, `matched_*_out.txt` |
| No-program control | `no_program_control.py` | `npc_*.json` |
| Wrong-answer classes; Q8_0 against Q4_K_M | `cafa_revision.py classify`, `q8` | `classify_*.txt`, `q8_out.txt` |
| Prompt controls (no demonstration, reversed, answer 8) | `cafa_revision.py rerun --demo`, `demo_sensitivity.py`, `demo8.py` | `rerun_*none*`, `rerun_*rev*`, `rerun_*orig8*`, `demo*_out.txt` |
| Generator variants (input 5, no padding) | `make_variants.py`, `variants_analysis.py` | `var_*_out.txt`, `variants_report.json` |
| Identifier-group checks | `name_ablation.py`, `name_ablation_readable.py` | pilot: `ablate_*.json`, `readable_*.json`; confirmation: `ablate_conf_*.json`, `readable_conf_*.json`, `idgroups_*_out.txt` |
| Ranking study of 15 models | `rank_analysis.py` | `rank_analysis_out.txt`, `rank_out/` |
| Worked example (Listing) | `show_example.py` | `example_out.txt` |

Docstrings written during the pilot refer to "Table VII": that is the main-effects table of an earlier draft, not a table of the
submitted paper.

## Pre-registrations

Three analyses were committed to this repository before the runs they govern:

| Analysis | File | Commit |
|---|---|---|
| Generator variants and answer-8 runs | `PREREG_variants.md` | `bd8e394dac364ac5a584299075f014210f13e04a` (2026-10-12 19:31 +0800) |
| 15-model ranking study | `PREREG_ranking.md` | `7a5416b6d108fe89955ca485630f06a5e6069673` (2026-10-12 22:07 +0800) |
| Identifier-group check on the confirmation set | `PREREG_idgroups.md` | `f9ee130c3b40b10fd61ab2def6883d2840f650f8` (2026-10-13 09:13 +0800) |

`PREREG_confirm.txt` records, with self-written UTC timestamps, the manifest digest and the analysis plan (2026-10-10 10:32:37 UTC, before any model was scored) and, appended later, the complete-case rule (2026-10-11 04:18:18 UTC, after scoring, when the skipped program 671 was found; it depends on missingness only). The file entered the repository after the runs, so no commit precedes them; the timestamps are not independently verifiable. The paper says so.

## Licence and citation

Code: MIT (`LICENSE`). Data derived from Project CodeNet keeps the CodeNet licence (see above); model weights are not included and keep
their own licences. Cite the paper and this archive (`CITATION.cff`).
