# Running G2 (steps 1 to 4 need no GPU and no model; do not score anything before the gates pass)

From `/data/workzone/capa`, env `cafa` (`conda activate cafa`). Copy `g2_features.py`, `g2_generate.py`, `g2_balance.py` and `PREREG_G2.md` here first.

0. Keep the earlier outputs: `mv g2_base.json g2_base_v2.json; mv g2_report.json g2_report_v2.json; mv g2_balance.md g2_balance_v2.md` (v1's are already `*_v1.*`).
   Commit the pre-registration and the three scripts before generating (fill the date and hash in `PREREG_G2.md` after the commit).
   `python3 g2_generate.py --selftest` must print `forms: 52 mismatches: 0`.
1. Generate: `python3 g2_generate.py --manifest manifest_confirm.json --out g2_base.json --jobs $(nproc) 2>&1 | tail -30`
   Gate A: `gate_A_pass` true (at least 95% of 1,542). `unmatched_attempt_failures` says why the rest failed.
2. Balance: `python3 g2_balance.py --manifest manifest_confirm.json --g2 g2_base.json --out g2_balance 2>&1 | tail -90`
   The output ends with the Gate B table and the selection check. G1's own balance: `python3 g2_balance.py --manifest manifest_confirm.json --out g1_balance`.
3. Read a few programs by eye (no editing): print `source_code` and `stdin_cases[0]` of the first 6 records of `g2_base.json`.
4. Send back `g2_report.json`, `g2_balance.md`. Next: manifest builder (conditions 4, 6, 8 with `identifier_rename.obfuscate_identifiers` and
   `ast_shuffle.shuffle_and_verify_script`), the execution audit for G2 (Gate C), the run script and the analysis.
