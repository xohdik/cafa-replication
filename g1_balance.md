# Covariate balance: generator programs against the real programs they were matched to

1542 samples with an executable program in every group. SMD = (generated - real) / pooled SD; |SMD| < 0.10 read as balanced. 'matched' rows were targeted by G2; G1's matching is described in the paper (lines, cyclomatic complexity, nesting depth, output shape).

| Covariate | role | real mean | G1 mean | G1 SMD | G1 KS |
|---|---|---|---|---|---|
| lines | matched | 26.85 | 31.50 | +0.16 | 0.07 |
| stmts | free | 25.73 | 31.50 | +0.20 | 0.09 |
| cc | matched | 8.88 | 7.76 | -0.15 | 0.07 |
| depth | matched | 2.90 | 2.94 | +0.02 | 0.04 |
| loops | free | 2.94 | 1.22 | -0.76 | 0.37 |
| ifs | free | 3.26 | 5.54 | +0.43 | 0.19 |
| comps | free | 1.00 | 0.00 | -0.84 | 0.42 |
| has_func | free | 0.41 | 0.00 | -1.17 | 0.41 |
| has_import | free | 0.40 | 0.05 | -0.91 | 0.34 |
| n_input_calls | free | 1.73 | 1.00 | -0.85 | 0.56 |
| uses_stdin_read | free | 0.19 | 0.00 | -0.68 | 0.19 |
| n_names | free | 11.75 | 20.00 | +0.50 | 0.18 |
| name_len_mean | matched | 2.26 | 4.59 | +2.20 | 0.81 |
| name_single_frac | matched | 0.61 | 0.15 | -2.06 | 0.80 |
| name_snake_frac | free | 0.04 | 0.08 | +0.45 | 0.56 |
| n_int_consts | free | 21.83 | 28.18 | +0.03 | 0.23 |
| n_str_consts | free | 1.98 | 0.00 | -0.60 | 0.55 |
| max_int_const | free | 3213867802153347.00 | 77.54 | -0.05 | 0.68 |
| chars | free | 788.67 | 734.85 | -0.02 | 0.07 |
| in_lines | matched | 4.72 | 2.00 | -0.58 | 0.51 |
| in_tokens | matched | 10.94 | 4.00 | -0.47 | 0.58 |
| in_int_frac | free | 0.84 | 1.00 | +0.70 | 0.23 |
| in_mean_digits | free | 1.26 | 1.00 | -0.33 | 0.33 |
| in_has_neg | free | 0.04 | 0.00 | -0.29 | 0.04 |
| in_distinct_tokens_frac | free | 0.75 | 0.75 | -0.01 | 0.53 |
| out_lines | free | 2.13 | 1.59 | -0.18 | 0.15 |
| out_shape | matched | 1.29 | 1.29 | +0.00 | 0.00 |
| out_tokens | free | 3.30 | 1.59 | -0.26 | 0.20 |
| out_int_frac | free | 0.75 | 1.00 | +0.83 | 0.28 |
| out_first_len | free | 5.65 | 1.84 | -0.06 | 0.21 |
| out_max_abs | free | 9085898716194662.00 | 561.61 | -0.04 | 0.50 |
| out_first_is_10 | free | 0.02 | 0.01 | -0.08 | 0.01 |

Within tolerance of the real program (lines +-10%, cyclomatic complexity +-15%, depth exact, output shape equal):

| Generator | lines | cc | depth | all three | output shape |
|---|---|---|---|---|---|
| G1 | 0.439 | 0.825 | 0.958 | 0.361 | 1.000 |
