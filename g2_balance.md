# Covariate balance: generator programs against the real programs they were matched to

1526 samples with an executable program in every group. SMD = (generated - real) / pooled SD; |SMD| < 0.10 read as balanced. 'matched' rows were targeted by G2; G1's matching is described in the paper (lines, cyclomatic complexity, nesting depth, output shape).

| Covariate | role | real mean | G1 mean | G1 SMD | G1 KS | G2 mean | G2 SMD | G2 KS | G2 vs G1 SMD |
|---|---|---|---|---|---|---|---|---|---|
| lines | matched | 26.70 | 31.28 | +0.16 | 0.07 | 27.14 | +0.02 | 0.02 | -0.15 |
| stmts | free | 25.64 | 31.28 | +0.20 | 0.09 | 26.16 | +0.02 | 0.03 | -0.18 |
| cc | matched | 8.82 | 7.69 | -0.15 | 0.07 | 9.33 | +0.06 | 0.03 | +0.21 |
| depth | matched | 2.88 | 2.92 | +0.02 | 0.04 | 2.88 | +0.00 | 0.00 | -0.02 |
| loops | free | 2.94 | 1.21 | -0.76 | 0.37 | 3.38 | +0.13 | 0.07 | +0.84 |
| ifs | free | 3.23 | 5.48 | +0.43 | 0.19 | 3.02 | -0.06 | 0.03 | -0.48 |
| comps | free | 1.01 | 0.00 | -0.84 | 0.43 | 1.19 | +0.12 | 0.20 | +1.21 |
| has_func | free | 0.41 | 0.00 | -1.17 | 0.41 | 0.27 | -0.30 | 0.14 | +0.85 |
| has_import | free | 0.40 | 0.05 | -0.92 | 0.35 | 0.55 | +0.30 | 0.15 | +1.30 |
| n_input_calls | free | 1.74 | 1.00 | -0.86 | 0.56 | 1.60 | -0.12 | 0.09 | +0.74 |
| uses_stdin_read | free | 0.19 | 0.00 | -0.68 | 0.19 | 0.16 | -0.08 | 0.03 | +0.61 |
| n_names | free | 11.73 | 19.87 | +0.50 | 0.18 | 16.01 | +0.37 | 0.15 | -0.22 |
| name_len_mean | matched | 2.25 | 4.60 | +2.29 | 0.82 | 2.19 | -0.06 | 0.06 | -2.46 |
| name_single_frac | matched | 0.61 | 0.14 | -2.10 | 0.81 | 0.60 | -0.04 | 0.04 | +2.03 |
| name_snake_frac | free | 0.04 | 0.08 | +0.45 | 0.56 | 0.03 | -0.19 | 0.06 | -0.80 |
| n_int_consts | free | 21.84 | 27.96 | +0.03 | 0.24 | 16.56 | -0.03 | 0.05 | -0.45 |
| n_str_consts | free | 1.91 | 0.00 | -0.63 | 0.54 | 0.76 | -0.36 | 0.20 | +0.72 |
| max_int_const | free | 3209655656277815.50 | 77.86 | -0.05 | 0.68 | 2881.95 | -0.05 | 0.49 | +0.92 |
| chars | free | 780.29 | 719.21 | -0.03 | 0.07 | 685.44 | -0.04 | 0.04 | -0.04 |
| in_lines | matched | 4.71 | 2.00 | -0.58 | 0.51 | 4.39 | -0.06 | 0.01 | +0.69 |
| in_tokens | matched | 10.89 | 4.00 | -0.46 | 0.58 | 9.63 | -0.07 | 0.02 | +0.65 |
| log_in_lines | matched | 1.43 | 1.10 | -0.68 | 0.51 | 1.42 | -0.02 | 0.01 | +0.68 |
| log_in_tokens | matched | 1.94 | 1.61 | -0.51 | 0.58 | 1.93 | -0.01 | 0.02 | +0.52 |
| in_int_frac | free | 0.84 | 1.00 | +0.69 | 0.22 | 0.84 | -0.00 | 0.03 | -0.66 |
| in_mean_digits | free | 1.27 | 1.00 | -0.33 | 0.33 | 1.20 | -0.07 | 0.05 | +0.33 |
| in_has_neg | free | 0.04 | 0.00 | -0.30 | 0.04 | 0.02 | -0.14 | 0.02 | +0.20 |
| in_distinct_tokens_frac | free | 0.75 | 0.75 | -0.01 | 0.53 | 0.80 | +0.19 | 0.08 | +0.30 |
| out_lines | free | 2.13 | 1.58 | -0.18 | 0.14 | 5.04 | +0.35 | 0.11 | +0.44 |
| out_shape | matched | 1.29 | 1.29 | +0.00 | 0.00 | 1.29 | +0.00 | 0.00 | +0.00 |
| out_tokens | free | 3.29 | 1.58 | -0.26 | 0.20 | 7.34 | +0.39 | 0.38 | +0.73 |
| out_int_frac | free | 0.75 | 1.00 | +0.83 | 0.28 | 0.88 | +0.36 | 0.19 | -0.62 |
| out_first_len | free | 5.63 | 1.84 | -0.06 | 0.21 | 9.93 | +0.07 | 0.31 | +0.70 |
| out_max_abs | free | 9073990592004308.00 | 142.42 | -0.04 | 0.50 | 802400690054.51 | -0.04 | 0.58 | +0.04 |
| out_first_is_10 | free | 0.02 | 0.01 | -0.07 | 0.01 | 0.00 | -0.11 | 0.01 | -0.04 |

Within tolerance of the real program (lines +-10%, cyclomatic complexity +-15%, depth exact, output shape equal):

| Generator | lines | cc | depth | all three | output shape |
|---|---|---|---|---|---|
| G1 | 0.437 | 0.825 | 0.959 | 0.359 | 1.000 |
| G2 | 0.982 | 0.965 | 0.990 | 0.953 | 1.000 |

Classifier AUC for real versus generated (5-fold, grouped by sample; 95% bootstrap interval over samples). 0.5 = indistinguishable.

| Comparison | numeric covariates | covariates not matched | character n-grams |
|---|---|---|---|
| G1_vs_real | 0.996 [0.994, 0.998] | 0.993 [0.990, 0.996] | 1.000 [1.000, 1.000] |
| G2_vs_real | 0.880 [0.870, 0.891] | 0.875 [0.864, 0.887] | 1.000 [1.000, 1.000] |

Gate B (|SMD| of G2 against real, matched covariates; PREREG_G2.md):

| Covariate | G2 SMD | threshold | pass |
|---|---|---|---|
| lines | +0.017 | 0.10 | yes |
| cc | +0.063 | 0.10 | yes |
| depth | +0.001 | 0.15 | yes |
| name_len_mean | -0.055 | 0.10 | yes |
| name_single_frac | -0.038 | 0.10 | yes |
| log_in_lines | -0.018 | 0.10 | yes |
| log_in_tokens | -0.006 | 0.10 | yes |
| out_shape | +0.000 | 0.10 | yes |
| all | | | PASS |

Selection check: 1526 samples matched, 16 not matched. Mean of the REAL program's covariates in each group:

| Covariate | matched | not matched | SMD |
|---|---|---|---|
| lines | 26.70 | 71.94 | +0.89 |
| cc | 8.82 | 19.31 | +0.61 |
| depth | 2.88 | 4.31 | +0.44 |
| name_len_mean | 2.25 | 4.06 | +0.81 |
| name_single_frac | 0.61 | 0.47 | -0.44 |
| log_in_tokens | 1.94 | 2.18 | +0.29 |
| loops | 2.94 | 4.56 | +0.39 |
| ifs | 3.23 | 8.12 | +0.63 |
