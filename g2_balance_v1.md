# Covariate balance: generator programs against the real programs they were matched to

1392 samples with an executable program in every group. SMD = (generated - real) / pooled SD; |SMD| < 0.10 read as balanced. 'matched' rows were targeted by G2; G1's matching is described in the paper (lines, cyclomatic complexity, nesting depth, output shape).

| Covariate | role | real mean | G1 mean | G1 SMD | G1 KS | G2 mean | G2 SMD | G2 KS | G2 vs G1 SMD |
|---|---|---|---|---|---|---|---|---|---|
| lines | matched | 23.84 | 27.88 | +0.16 | 0.08 | 24.29 | +0.02 | 0.02 | -0.15 |
| stmts | free | 22.98 | 27.88 | +0.20 | 0.09 | 23.65 | +0.03 | 0.03 | -0.18 |
| cc | matched | 7.80 | 6.75 | -0.17 | 0.07 | 8.51 | +0.10 | 0.04 | +0.26 |
| depth | matched | 2.56 | 2.61 | +0.03 | 0.04 | 2.40 | -0.13 | 0.07 | -0.17 |
| loops | free | 2.64 | 1.05 | -0.79 | 0.40 | 3.12 | +0.15 | 0.05 | +0.84 |
| ifs | free | 2.69 | 4.70 | +0.47 | 0.20 | 2.63 | -0.02 | 0.03 | -0.49 |
| comps | free | 0.93 | 0.00 | -0.82 | 0.41 | 1.15 | +0.15 | 0.24 | +1.23 |
| has_func | free | 0.38 | 0.00 | -1.12 | 0.38 | 0.28 | -0.21 | 0.10 | +0.89 |
| has_import | free | 0.39 | 0.06 | -0.87 | 0.33 | 0.57 | +0.36 | 0.18 | +1.32 |
| n_input_calls | free | 1.71 | 1.00 | -0.86 | 0.56 | 1.55 | -0.14 | 0.10 | +0.68 |
| uses_stdin_read | free | 0.18 | 0.00 | -0.65 | 0.18 | 0.18 | -0.00 | 0.00 | +0.65 |
| n_names | free | 11.02 | 17.87 | +0.48 | 0.17 | 14.73 | +0.35 | 0.15 | -0.20 |
| name_len_mean | matched | 2.21 | 4.55 | +2.27 | 0.81 | 1.95 | -0.26 | 0.13 | -2.79 |
| name_single_frac | matched | 0.62 | 0.15 | -2.09 | 0.80 | 0.67 | +0.18 | 0.12 | +2.26 |
| name_snake_frac | free | 0.04 | 0.08 | +0.42 | 0.55 | 0.02 | -0.29 | 0.09 | -0.94 |
| n_int_consts | free | 20.73 | 24.72 | +0.02 | 0.24 | 14.03 | -0.03 | 0.04 | -0.50 |
| n_str_consts | free | 1.60 | 0.00 | -0.66 | 0.52 | 0.69 | -0.35 | 0.21 | +0.68 |
| max_int_const | free | 1862134707598040.75 | 76.34 | -0.04 | 0.67 | 2572.80 | -0.04 | 0.49 | +0.85 |
| chars | free | 701.00 | 582.65 | -0.05 | 0.08 | 512.13 | -0.08 | 0.08 | -0.12 |
| in_lines | matched | 4.21 | 2.00 | -0.56 | 0.49 | 4.01 | -0.04 | 0.01 | +0.64 |
| in_tokens | matched | 9.85 | 4.00 | -0.44 | 0.56 | 8.85 | -0.06 | 0.02 | +0.61 |
| log_in_lines | matched | 1.38 | 1.10 | -0.61 | 0.49 | 1.37 | -0.01 | 0.01 | +0.61 |
| log_in_tokens | matched | 1.88 | 1.61 | -0.44 | 0.56 | 1.88 | -0.00 | 0.02 | +0.45 |
| in_int_frac | free | 0.86 | 1.00 | +0.64 | 0.20 | 0.86 | +0.02 | 0.03 | -0.61 |
| in_mean_digits | free | 1.27 | 1.00 | -0.34 | 0.33 | 1.21 | -0.06 | 0.05 | +0.35 |
| in_has_neg | free | 0.04 | 0.00 | -0.30 | 0.04 | 0.02 | -0.13 | 0.02 | +0.20 |
| in_distinct_tokens_frac | free | 0.76 | 0.75 | -0.06 | 0.54 | 0.80 | +0.15 | 0.07 | +0.29 |
| out_lines | free | 2.03 | 1.54 | -0.16 | 0.13 | 3.78 | +0.27 | 0.08 | +0.38 |
| out_shape | matched | 1.27 | 1.27 | +0.00 | 0.00 | 1.27 | +0.00 | 0.00 | +0.00 |
| out_tokens | free | 3.18 | 1.54 | -0.24 | 0.18 | 6.02 | +0.31 | 0.38 | +0.72 |
| out_int_frac | free | 0.75 | 1.00 | +0.83 | 0.27 | 0.89 | +0.37 | 0.18 | -0.59 |
| out_first_len | free | 5.84 | 1.74 | -0.06 | 0.27 | 8.97 | +0.05 | 0.30 | +0.76 |
| out_max_abs | free | 9947492558937710.00 | 61.77 | -0.04 | 0.48 | 4951348479.74 | -0.04 | 0.55 | +0.05 |
| out_first_is_10 | free | 0.01 | 0.01 | -0.05 | 0.01 | 0.01 | -0.07 | 0.01 | -0.03 |

Within tolerance of the real program (lines +-10%, cyclomatic complexity +-15%, depth exact, output shape equal):

| Generator | lines | cc | depth | all three | output shape |
|---|---|---|---|---|---|
| G1 | 0.443 | 0.823 | 0.955 | 0.362 | 1.000 |
| G2 | 0.979 | 0.905 | 0.825 | 0.810 | 1.000 |

Classifier AUC for real versus generated (5-fold, grouped by sample; 95% bootstrap interval over samples). 0.5 = indistinguishable.

| Comparison | numeric covariates | covariates not matched | character n-grams |
|---|---|---|---|
| G1_vs_real | 0.997 [0.994, 0.999] | 0.993 [0.990, 0.996] | 1.000 [1.000, 1.000] |
| G2_vs_real | 0.878 [0.868, 0.889] | 0.872 [0.861, 0.883] | 1.000 [1.000, 1.000] |

Gate B (|SMD| of G2 against real, matched covariates; PREREG_G2.md):

| Covariate | G2 SMD | threshold | pass |
|---|---|---|---|
| lines | +0.020 | 0.10 | yes |
| cc | +0.101 | 0.10 | NO |
| depth | -0.127 | 0.15 | yes |
| name_len_mean | -0.256 | 0.10 | NO |
| name_single_frac | +0.178 | 0.10 | NO |
| log_in_lines | -0.013 | 0.10 | yes |
| log_in_tokens | -0.003 | 0.10 | yes |
| out_shape | +0.000 | 0.10 | yes |
| all | | | FAIL |

Selection check: 1392 samples matched, 150 not matched. Mean of the REAL program's covariates in each group:

| Covariate | matched | not matched | SMD |
|---|---|---|---|
| lines | 23.84 | 58.07 | +1.00 |
| cc | 7.80 | 19.39 | +1.12 |
| depth | 2.56 | 5.97 | +2.08 |
| name_len_mean | 2.21 | 2.72 | +0.39 |
| name_single_frac | 0.62 | 0.49 | -0.56 |
| log_in_tokens | 1.88 | 2.45 | +0.57 |
| loops | 2.64 | 5.93 | +0.85 |
| ifs | 2.69 | 8.77 | +1.15 |
