#!/usr/bin/env bash
cd /data/workzone/capa
mkdir -p g2_out
M=manifest_g2.json
gg(){ python3 -c "import json;print(json.loads(open('$1').readline())['gguf'])"; }
DS=models/$(gg rerun_ds_q4.jsonl); SC=models/$(gg rerun_sc2_q4.jsonl); CL=models/$(gg rerun_cl_q4.jsonl)
Q7=models/$(gg rerun_q7_q4.jsonl); Q14=models/$(gg rerun_q14_q4.jsonl)
run(){ CUDA_VISIBLE_DEVICES=$1 python3 cafa_revision.py rerun --manifest $M --gguf "$2" --conditions $3 --demo $4 --out "g2_out/$5" >> g2_out/log_gpu$1.txt 2>&1; }
main(){ run $1 "$3" 2,4,6,8 orig e1_$2.jsonl; run $1 "$3" 2,6 none e2_$2.jsonl; }
other(){ run $1 "models/$3" 2 orig e3_$2_orig.jsonl; run $1 "models/$3" 2 none e3_$2_none.jsonl; }
case $1 in
 0) main 0 ds "$DS"; main 0 sc2 "$SC"; main 0 q7 "$Q7"
    other 0 yi9 Yi-Coder-9B.Q4_K_M.gguf; other 0 cg7 codegemma-7b.Q4_K_M.gguf; other 0 gr3 granite-3b-code-base-128k.Q4_K_M.gguf
    other 0 sc3 starcoder2-3b-Q4_K_M.gguf; other 0 q3 Qwen2.5-Coder-3B.Q4_K_M.gguf; other 0 q15 Qwen2.5-Coder-1.5B.Q4_K_M.gguf
    other 0 ds13 deepseek-coder-1.3b-base.Q4_K_M.gguf ;;
 1) main 1 cl "$CL"; main 1 q14 "$Q14"
    other 1 sc15 starcoder2-15b-Q4_K_M.gguf; other 1 cl13 codellama-13b.Q4_K_M.gguf; other 1 gr8 granite-8b-code-base-128k.Q4_K_M.gguf ;;
esac
echo "GPU $1 queue finished" >> g2_out/log_gpu$1.txt
