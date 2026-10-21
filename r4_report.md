# Revision 4: multi-input oracle (1542 real programs; real = conditions 1, 3, 5, 7; G1 = conditions 2, 4, 6, 8)

- official CodeNet input found: 1542; equals stdin_cases[0]: 1542
- real program runs on the official input: 1542; reproduces the official output: 1431
- reference solutions per problem (0 / 1 / 2 / 3 or more): 49 / 30 / 24 / 1439
- extra valid inputs per program (0 / 1 / 2): 225 / 65 / 1252
- accepted inputs by tier: A 2514, B 55; with output different from the official output: 2251 of 2569

## Real conditions against condition 1 (programs with the condition's code changed from condition 1; 'first only' = passes the official input but differs or fails on an extra input)

| condition | changed | equal on every available input | equal on first input only | differs or errors on the official input | programs with >= 1 extra input |
|---|---|---|---|---|---|
| 3 (shuffle) | 542 | 542 | 0 | 0 | 452 |
| 5 (obfuscation) | 1542 | 1542 | 0 | 0 | 1317 |
| 7 (both) | 1542 | 1542 | 0 | 0 | 1317 |

- programs where at least one real condition fails on an extra input: 0

## G1 conditions (2, 4, 6, 8) on their three stdin cases

- samples with a run error in any G1 condition: 0; with differing outputs between conditions on some case: 0