# Post hoc: accuracy by expected output length (original prompt; A original)

| model | source | 1 token | 2-3 | 4-6 | 7+ | all |
|---|---|---|---|---|---|---|
| DeepSeek-Coder-6.7B | real |  41.1 (n=1002) |  12.0 (n=233) |   7.8 (n=167) |   3.6 (n=139) | 29.7 |
| DeepSeek-Coder-6.7B | G1 |  17.3 (n=1090) |   4.0 (n=452) |    -    |    -    | 13.4 |
| DeepSeek-Coder-6.7B | G2 |  21.4 (n=842) |   8.2 (n=766) |   3.5 (n=566) |   0.0 (n=878) | 8.6 |
| StarCoder2 | real |  33.7 (n=1002) |   9.0 (n=233) |   4.2 (n=167) |   1.4 (n=139) | 23.9 |
| StarCoder2 | G1 |  16.2 (n=1090) |   5.5 (n=452) |    -    |    -    | 13.1 |
| StarCoder2 | G2 |  21.1 (n=842) |   6.5 (n=766) |   2.5 (n=566) |   0.1 (n=878) | 8.0 |
| CodeLlama | real |  29.4 (n=2004) |   9.0 (n=466) |   1.5 (n=334) |   0.7 (n=278) | 20.7 |
| CodeLlama | G1 |  23.3 (n=2180) |   5.0 (n=904) |    -    |    -    | 17.9 |
| CodeLlama | G2 |  20.1 (n=842) |   6.7 (n=766) |   2.7 (n=566) |   0.0 (n=878) | 7.7 |
| Qwen2.5-Coder-7B | real |  36.9 (n=2004) |  14.6 (n=466) |   7.2 (n=334) |   3.6 (n=278) | 27.3 |
| Qwen2.5-Coder-7B | G1 |  35.1 (n=2180) |   9.7 (n=904) |    -    |    -    | 27.7 |
| Qwen2.5-Coder-7B | G2 |  24.0 (n=842) |  10.6 (n=766) |   4.1 (n=566) |   0.7 (n=878) | 10.2 |
| Qwen2.5-Coder-14B | real |  43.2 (n=2004) |  18.5 (n=466) |  12.6 (n=334) |   5.0 (n=278) | 32.7 |
| Qwen2.5-Coder-14B | G1 |  46.4 (n=2180) |  11.1 (n=904) |    -    |    -    | 36.0 |
| Qwen2.5-Coder-14B | G2 |  26.7 (n=842) |  14.6 (n=766) |   6.4 (n=566) |   0.9 (n=878) | 12.5 |

# Post hoc: source effect (G2 minus real, mean of conditions (2,6) minus (1,5)) on samples whose real AND G2 outputs are both a single token

| model | n | real | G2 | G2 - real [95%] | all-sample G2 - real (for reference) |
|---|---|---|---|---|---|
| DeepSeek-Coder-6.7B | 0 | too few | | | |
| StarCoder2 | 0 | too few | | | |
| CodeLlama | 385 | 33.4 | 20.6 | -12.73 [-18.44, -7.14] | -12.79 |
| Qwen2.5-Coder-7B | 385 | 42.1 | 24.4 | -17.66 [-23.64, -11.82] | -16.98 |
| Qwen2.5-Coder-14B | 385 | 48.4 | 27.4 | -21.04 [-26.62, -15.45] | -20.03 |