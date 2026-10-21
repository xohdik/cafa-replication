#!/usr/bin/env bash
# run_r4.sh GPU_ID -- conditions 1 and 5 on the extra inputs (PREREG_R4.md). Resumable.
cd /data/workzone/capa
mkdir -p r4_out
gg(){ python3 -c "import json;print(json.loads(open('$1').readline())['gguf'])"; }
DS=models/$(gg rerun_ds_q4.jsonl); SC=models/$(gg rerun_sc2_q4.jsonl); CL=models/$(gg rerun_cl_q4.jsonl)
Q7=models/$(gg rerun_q7_q4.jsonl); Q14=models/$(gg rerun_q14_q4.jsonl)
run(){ CUDA_VISIBLE_DEVICES=$1 python3 cafa_revision.py rerun --manifest manifest_r4_x${4}.json --gguf "$2" --conditions 1,5 --demo orig --out "r4_out/x${4}_${3}.jsonl" >> r4_out/log_gpu$1.txt 2>&1; }
both(){ run $1 "$3" $2 1; run $1 "$3" $2 2; }
case $1 in
 0) both 0 ds "$DS"; both 0 sc2 "$SC"; both 0 q7 "$Q7" ;;
 1) both 1 cl "$CL"; both 1 q14 "$Q14" ;;
esac
echo "GPU $1 queue finished" >> r4_out/log_gpu$1.txt
