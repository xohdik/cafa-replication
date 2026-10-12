#!/bin/bash
# Part 2B: generator variants (DeepSeek-Coder, StarCoder2; condition 2 only) and answer-8 demonstration for the other three models.
# Run after: python3 make_variants.py   (writes manifest_var_n5.json, manifest_var_nopad.json)
DS=models/deepseek-coder-6.7b-base.Q4_K_M.gguf
SC=models/starcoder2-7b-Q4_K_M.gguf
CL=models/codellama-7b.Q4_K_M.gguf
Q7=models/Qwen2.5-Coder-7B.Q4_K_M.gguf
Q14=models/Qwen2.5-Coder-14B.Q4_K_M.gguf
gpu0() {
  for v in n5 nopad; do
    CUDA_VISIBLE_DEVICES=0 python3 cafa_revision.py rerun --manifest manifest_var_$v.json --gguf $DS --conditions 2 --demo orig --out rerun_dsvar_${v}_q4.jsonl
  done
  CUDA_VISIBLE_DEVICES=0 python3 cafa_revision.py rerun --gguf $Q14 --conditions 1,2,5,6 --demo orig8 --out rerun_q14orig8_q4.jsonl
}
gpu1() {
  for v in n5 nopad; do
    CUDA_VISIBLE_DEVICES=1 python3 cafa_revision.py rerun --manifest manifest_var_$v.json --gguf $SC --conditions 2 --demo orig --out rerun_sc2var_${v}_q4.jsonl
  done
  CUDA_VISIBLE_DEVICES=1 python3 cafa_revision.py rerun --gguf $CL --conditions 1,2,5,6 --demo orig8 --out rerun_clorig8_q4.jsonl
  CUDA_VISIBLE_DEVICES=1 python3 cafa_revision.py rerun --gguf $Q7 --conditions 1,2,5,6 --demo orig8 --out rerun_q7orig8_q4.jsonl
}
gpu0 > log_p2b_gpu0.txt 2>&1 &
gpu1 > log_p2b_gpu1.txt 2>&1 &
wait
echo "part 2B runs finished" | tee -a log_p2b_done.txt
