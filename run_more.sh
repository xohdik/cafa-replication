cd "$(dirname "$0")"
q(){ CUDA_VISIBLE_DEVICES=$1 python3 cafa_revision.py rerun --gguf models/$2 --conditions 1,2,5,6 --out $3 ${4:+--demo $4}; }
( q 0 codellama-7b.Q4_K_M.gguf rerun_cl_q4.jsonl; q 0 codellama-7b.Q4_K_M.gguf rerun_clnone_q4.jsonl none; q 0 Qwen2.5-Coder-7B.Q4_K_M.gguf rerun_q7_q4.jsonl; q 0 Qwen2.5-Coder-7B.Q4_K_M.gguf rerun_q7none_q4.jsonl none ) > log_more0.txt 2>&1 &
( q 1 Qwen2.5-Coder-14B.Q4_K_M.gguf rerun_q14_q4.jsonl; q 1 Qwen2.5-Coder-14B.Q4_K_M.gguf rerun_q14none_q4.jsonl none ) > log_more1.txt 2>&1 &
