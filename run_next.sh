cd "$(dirname "$0")"
M=models/deepseek-coder-6.7b-base.Q4_K_M.gguf
S=models/starcoder2-7b-Q4_K_M.gguf
( export CUDA_VISIBLE_DEVICES=0; python3 cafa_revision.py rerun --gguf $M --conditions 1,2,5,6 --out rerun_dsorig8_q4.jsonl --demo orig8; python3 check_b.py $M orig tenprob_ds_orig.jsonl; python3 check_b.py $M none tenprob_ds_none.jsonl ) > log_next0.txt 2>&1 &
( export CUDA_VISIBLE_DEVICES=1; python3 cafa_revision.py rerun --gguf $S --conditions 1,2,5,6 --out rerun_sc2orig8_q4.jsonl --demo orig8 ) > log_next1.txt 2>&1 &
