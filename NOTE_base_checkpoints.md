# Note: base-checkpoint check of the models (written after the runs)

Date: 2026-10-13. Status: **post hoc**; it completes fields that `PREREG_ranking.md` (commit 7a5416b6d108fe89955ca485630f06a5e6069673)
left open ("confirm on its model card: [yes/no]"). The registered file is unchanged and no model, file or result changed because of this note.

## Method
For each GGUF repository used, the upstream model recorded in the repository's card metadata (`base_model`) was read through the
Hugging Face API (`HfApi().model_info(repo).card_data.base_model`, via the hf-mirror endpoint of the server) on 2026-10-13. For six of the
ten ranking-study repositories the repository page was also read by hand on the same day. Each local file was matched to its repository
by SHA-256 (`MODEL_SHA256.txt`).

## Result
| Model | GGUF repository | Upstream recorded in the card | Base (not instruction-tuned) |
|---|---|---|---|
| DeepSeek-Coder-1.3B | TheBloke/deepseek-coder-1.3b-base-GGUF | deepseek-ai/deepseek-coder-1.3b-base | yes |
| Qwen2.5-Coder-1.5B | mradermacher/Qwen2.5-Coder-1.5B-GGUF | Qwen/Qwen2.5-Coder-1.5B | yes |
| Qwen2.5-Coder-3B | mradermacher/Qwen2.5-Coder-3B-GGUF | Qwen/Qwen2.5-Coder-3B | yes |
| StarCoder2-3B | second-state/StarCoder2-3B-GGUF | bigcode/starcoder2-3b | yes |
| StarCoder2-15B | second-state/StarCoder2-15B-GGUF | bigcode/starcoder2-15b | yes |
| CodeLlama-13B | TheBloke/CodeLlama-13B-GGUF | codellama/CodeLlama-13b-hf | yes |
| CodeGemma-7B | mradermacher/codegemma-7b-GGUF | google/codegemma-7b | yes |
| Granite-Code-3B-128k | mradermacher/granite-3b-code-base-128k-GGUF | ibm-granite/granite-3b-code-base-128k | yes |
| Granite-Code-8B-128k | mradermacher/granite-8b-code-base-128k-GGUF | ibm-granite/granite-8b-code-base-128k | yes |
| Yi-Coder-9B | mradermacher/Yi-Coder-9B-GGUF | 01-ai/Yi-Coder-9B | yes |

The five models of the main study, checked the same way:

| Model | GGUF repository | Upstream recorded in the card | Base |
|---|---|---|---|
| DeepSeek-Coder-6.7B | TheBloke/deepseek-coder-6.7B-base-GGUF | deepseek-ai/deepseek-coder-6.7b-base | yes |
| CodeLlama-7B | TheBloke/CodeLlama-7B-GGUF | codellama/CodeLlama-7b-hf | yes |
| StarCoder2-7B | second-state/StarCoder2-7B-GGUF | bigcode/starcoder2-7b | yes |
| Qwen2.5-Coder-7B | QuantFactory/Qwen2.5-Coder-7B-GGUF | Qwen/Qwen2.5-7B (see below) | yes, by repository and file name |
| Qwen2.5-Coder-14B | QuantFactory/Qwen2.5-Coder-14B-GGUF | Qwen/Qwen2.5-14B (see below) | yes, by repository and file name |

## Limits
- The check reads repository metadata; the weights were not inspected. A repository can mislabel its upstream.
- The QuantFactory cards for Qwen2.5-Coder-7B and -14B record the general model they were trained from (Qwen2.5-7B, Qwen2.5-14B),
  as Qwen's own cards do, not Qwen2.5-Coder; the repository names and file names (`Qwen2.5-Coder-7B`, no `Instruct`) identify the
  Coder base models. The files themselves were matched to these repositories by SHA-256.
- "Base" here means not an instruction- or chat-tuned release as named in the repository; none of the cards mentions
  instruction tuning.
