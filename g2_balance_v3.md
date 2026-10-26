# Covariate balance: generator programs against the real programs they were matched to

1522 samples with an executable program in every group. SMD = (generated - real) / pooled SD; |SMD| < 0.10 read as balanced. 'matched' rows were targeted by G2; G1's matching is described in the paper (lines, cyclomatic complexity, nesting depth, output shape).

| Covariate | role | real mean | G1 mean | G1 SMD | G1 KS | G2 mean | G2 SMD | G2 KS | G2 vs G1 SMD |
|---|---|---|---|---|---|---|---|---|---|
| lines | matched | 26.56 | 31.13 | +0.16 | 0.07 | 27.43 | +0.03 | 0.03 | -0.13 |
| stmts | free | 25.52 | 31.13 | +0.20 | 0.09 | 26.33 | +0.03 | 0.03 | -0.17 |
| cc | matched | 8.79 | 7.68 | -0.15 | 0.07 | 9.57 | +0.10 | 0.05 | +0.24 |
| depth | matched | 2.88 | 2.92 | +0.02 | 0.04 | 2.88 | +0.00 | 0.00 | -0.02 |
| loops | free | 2.94 | 1.21 | -0.75 | 0.37 | 3.32 | +0.12 | 0.05 | +0.82 |
| ifs | free | 3.22 | 5.47 | +0.43 | 0.19 | 3.13 | -0.03 | 0.02 | -0.45 |
| comps | free | 1.00 | 0.00 | -0.85 | 0.43 | 1.27 | +0.17 | 0.24 | +1.26 |
| has_func | free | 0.41 | 0.00 | -1.17 | 0.41 | 0.29 | -0.25 | 0.12 | +0.90 |
| has_import | free | 0.40 | 0.05 | -0.92 | 0.35 | 0.58 | +0.36 | 0.18 | +1.37 |
| n_input_calls | free | 1.74 | 1.00 | -0.87 | 0.56 | 1.59 | -0.13 | 0.09 | +0.74 |
| uses_stdin_read | free | 0.19 | 0.00 | -0.67 | 0.19 | 0.15 | -0.09 | 0.03 | +0.60 |
| n_names | free | 11.66 | 19.75 | +0.51 | 0.18 | 15.93 | +0.38 | 0.15 | -0.22 |
| name_len_mean | matched | 2.24 | 4.59 | +2.29 | 0.81 | 2.00 | -0.23 | 0.12 | -2.74 |
| name_single_frac | matched | 0.61 | 0.14 | -2.11 | 0.81 | 0.66 | +0.19 | 0.11 | +2.28 |
| name_snake_frac | free | 0.04 | 0.08 | +0.46 | 0.56 | 0.02 | -0.24 | 0.08 | -0.87 |
| n_int_consts | free | 21.78 | 27.82 | +0.03 | 0.24 | 16.68 | -0.03 | 0.07 | -0.45 |
| n_str_consts | free | 1.91 | 0.00 | -0.62 | 0.54 | 0.77 | -0.35 | 0.19 | +0.74 |
| max_int_const | free | 3218091018713337.50 | 77.81 | -0.05 | 0.68 | 3014.26 | -0.05 | 0.50 | +0.95 |
| chars | free | 776.91 | 715.46 | -0.03 | 0.07 | 682.28 | -0.04 | 0.03 | -0.04 |
| in_lines | matched | 4.71 | 2.00 | -0.58 | 0.51 | 4.39 | -0.06 | 0.01 | +0.68 |
| in_tokens | matched | 10.89 | 4.00 | -0.46 | 0.58 | 9.63 | -0.07 | 0.02 | +0.65 |
| log_in_lines | matched | 1.43 | 1.10 | -0.68 | 0.51 | 1.42 | -0.02 | 0.01 | +0.68 |
| log_in_tokens | matched | 1.94 | 1.61 | -0.50 | 0.58 | 1.93 | -0.01 | 0.02 | +0.51 |
| in_int_frac | free | 0.84 | 1.00 | +0.69 | 0.23 | 0.84 | -0.00 | 0.03 | -0.66 |
| in_mean_digits | free | 1.27 | 1.00 | -0.33 | 0.33 | 1.20 | -0.07 | 0.05 | +0.33 |
| in_has_neg | free | 0.04 | 0.00 | -0.30 | 0.04 | 0.02 | -0.10 | 0.02 | +0.22 |
| in_distinct_tokens_frac | free | 0.75 | 0.75 | -0.01 | 0.53 | 0.80 | +0.19 | 0.09 | +0.29 |
| out_lines | free | 2.12 | 1.58 | -0.18 | 0.14 | 4.88 | +0.34 | 0.11 | +0.44 |
| out_shape | matched | 1.29 | 1.29 | +0.00 | 0.00 | 1.29 | +0.00 | 0.00 | +0.00 |
| out_tokens | free | 3.29 | 1.58 | -0.26 | 0.20 | 7.13 | +0.38 | 0.36 | +0.73 |
| out_int_frac | free | 0.75 | 1.00 | +0.83 | 0.28 | 0.87 | +0.34 | 0.18 | -0.63 |
| out_first_len | free | 5.62 | 1.84 | -0.06 | 0.21 | 9.28 | +0.06 | 0.28 | +0.75 |
| out_max_abs | free | 9097838136267132.00 | 142.31 | -0.04 | 0.50 | 3792293335.52 | -0.04 | 0.57 | +0.04 |
| out_first_is_10 | free | 0.02 | 0.01 | -0.08 | 0.01 | 0.00 | -0.12 | 0.01 | -0.05 |

Within tolerance of the real program (lines +-10%, cyclomatic complexity +-15%, depth exact, output shape equal):

| Generator | lines | cc | depth | all three | output shape |
|---|---|---|---|---|---|
| G1 | 0.437 | 0.825 | 0.959 | 0.359 | 1.000 |
| G2 | 0.980 | 0.959 | 0.990 | 0.947 | 1.000 |

Classifier AUC for real versus generated (5-fold, grouped by sample; 95% bootstrap interval over samples). 0.5 = indistinguishable.

| Comparison | numeric covariates | covariates not matched | character n-grams |
|---|---|---|---|
| G1_vs_real | 0.997 [0.994, 0.998] | 0.994 [0.991, 0.996] | 1.000 [1.000, 1.000] |
| G2_vs_real | 0.881 [0.869, 0.892] | 0.872 [0.860, 0.884] | 1.000 [0.999, 1.000] |

Gate B (|SMD| of G2 against real, matched covariates; PREREG_G2.md):

| Covariate | G2 SMD | threshold | pass |
|---|---|---|---|
| lines | +0.034 | 0.10 | yes |
| cc | +0.095 | 0.10 | yes |
| depth | +0.000 | 0.15 | yes |
| name_len_mean | -0.229 | 0.10 | NO |
| name_single_frac | +0.186 | 0.10 | NO |
| log_in_lines | -0.018 | 0.10 | yes |
| log_in_tokens | -0.006 | 0.10 | yes |
| out_shape | +0.000 | 0.10 | yes |
| all | | | FAIL |

Selection check: 1522 samples matched, 20 not matched. Mean of the REAL program's covariates in each group:

| Covariate | matched | not matched | SMD |
|---|---|---|---|
| lines | 26.56 | 73.45 | +0.97 |
| cc | 8.79 | 18.95 | +0.63 |
| depth | 2.88 | 4.10 | +0.40 |
| name_len_mean | 2.24 | 3.76 | +0.73 |
| name_single_frac | 0.61 | 0.43 | -0.59 |
| log_in_tokens | 1.94 | 2.22 | +0.35 |
| loops | 2.94 | 4.75 | +0.46 |
| ifs | 3.22 | 7.65 | +0.62 |
