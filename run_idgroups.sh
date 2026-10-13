#!/bin/bash
# Part 2C: identifier-group checks on the confirmation set (DeepSeek-Coder-6.7B on GPU 0, Qwen2.5-Coder-7B on GPU 1).
# Pilot outputs ablate_*.json / readable_*.json are NOT overwritten; new files are *_conf_*.json. Scripts are resumable.
cd "$(dirname "$0")"
DS=models/deepseek-coder-6.7b-base.Q4_K_M.gguf
Q7=models/Qwen2.5-Coder-7B.Q4_K_M.gguf
run() {  # $1 = gpu, $2 = gguf, $3 = tag
  CUDA_VISIBLE_DEVICES=$1 python3 name_ablation.py --manifest manifest_confirm.json --gguf $2 --out ablate_conf_$3.json
  CUDA_VISIBLE_DEVICES=$1 python3 name_ablation_readable.py --manifest manifest_confirm.json --gguf $2 --out readable_conf_$3.json
}
run 0 $DS ds > idgroups_ds_out.txt 2>&1 &
run 1 $Q7 q7 > idgroups_q7_out.txt 2>&1 &
wait
echo "identifier-group runs finished" | tee -a log_idgroups_done.txt
