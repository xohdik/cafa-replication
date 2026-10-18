# H4: ranking of 15 models on real, G1 and G2 programs (PREREG_G2.md)


## Prompt: orig  (15 models, 1525 programs scored for every model under real, G1 and G2)

| model | real % | G1 % | G2 % | rank real | rank G1 | rank G2 |
|---|---|---|---|---|---|---|
| Qwen2.5-Coder-14B | 34.2 | 37.4 | 12.5 | 1 | 1 | 1 |
| Yi-Coder-9B | 33.0 | 27.5 | 9.8 | 2 | 3 | 4 |
| StarCoder2-15B | 30.1 | 25.2 | 10.2 | 3 | 5 | 3 |
| DeepSeek-Coder-6.7B | 29.6 | 13.6 | 8.3 | 4 | 11 | 6 |
| Qwen2.5-Coder-7B | 28.5 | 29.7 | 10.2 | 5 | 2 | 2 |
| Granite-Code-8B-128k | 25.2 | 14.0 | 8.1 | 6 | 10 | 7.5 |
| CodeGemma-7B | 25.1 | 27.0 | 7.9 | 7 | 4 | 10 |
| Qwen2.5-Coder-3B | 24.1 | 18.7 | 8.9 | 8 | 7 | 5 |
| CodeLlama-13B | 23.9 | 24.4 | 8.1 | 9 | 6 | 7.5 |
| StarCoder2-7B | 23.7 | 13.0 | 7.9 | 10 | 12 | 9 |
| StarCoder2-3B | 21.6 | 15.8 | 7.3 | 11 | 9 | 13 |
| Qwen2.5-Coder-1.5B | 21.2 | 10.0 | 7.5 | 12 | 14 | 12 |
| CodeLlama-7B | 20.9 | 17.9 | 7.7 | 13 | 8 | 11 |
| DeepSeek-Coder-1.3B | 20.0 | 12.5 | 5.9 | 14 | 13 | 15 |
| Granite-Code-3B-128k | 18.4 | 5.4 | 7.2 | 15 | 15 | 14 |

- real vs G2: tau-b = 0.746 [95% CI 0.543, 0.812]; discordant pairs 12.4% of 105; among 84 pairs resolved on real programs, 3 flip
- split-half noise ceiling (real vs real): median 0.850, 5th percentile 0.779 -> **material (instability replicates): True**
- reference, real vs G1 on the same programs: tau-b = 0.600 [0.478, 0.657]; discordant 20.0%; material: True
- G1 vs G2 orderings: tau-b = 0.632
- split-half ceiling within G2 programs: median 0.689, 5th percentile 0.559

## Prompt: none  (15 models, 1525 programs scored for every model under real, G1 and G2)

| model | real % | G1 % | G2 % | rank real | rank G1 | rank G2 |
|---|---|---|---|---|---|---|
| Yi-Coder-9B | 30.1 | 22.3 | 9.0 | 1 | 4 | 4 |
| Qwen2.5-Coder-14B | 28.3 | 29.6 | 11.4 | 2 | 1 | 1 |
| Qwen2.5-Coder-7B | 26.0 | 16.7 | 10.2 | 3 | 8 | 2 |
| CodeGemma-7B | 24.5 | 24.2 | 8.2 | 4 | 2 | 6 |
| Qwen2.5-Coder-3B | 23.2 | 21.7 | 8.5 | 5 | 5 | 5 |
| DeepSeek-Coder-6.7B | 23.0 | 23.0 | 7.5 | 6 | 3 | 7 |
| StarCoder2-15B | 21.5 | 17.2 | 9.2 | 7 | 7 | 3 |
| Qwen2.5-Coder-1.5B | 18.5 | 12.4 | 6.6 | 8 | 12 | 10 |
| CodeLlama-13B | 18.4 | 15.7 | 7.3 | 9 | 9 | 8 |
| StarCoder2-7B | 16.2 | 9.0 | 6.8 | 10 | 14 | 9 |
| StarCoder2-3B | 15.3 | 15.7 | 6.0 | 11 | 10 | 12 |
| CodeLlama-7B | 15.0 | 20.1 | 6.4 | 12 | 6 | 11 |
| DeepSeek-Coder-1.3B | 13.2 | 11.0 | 5.1 | 13 | 13 | 14 |
| Granite-Code-8B-128k | 10.4 | 14.5 | 5.9 | 14 | 11 | 13 |
| Granite-Code-3B-128k | 7.0 | 0.3 | 1.8 | 15 | 15 | 15 |

- real vs G2: tau-b = 0.790 [95% CI 0.689, 0.856]; discordant pairs 10.5% of 105; among 94 pairs resolved on real programs, 5 flip
- split-half noise ceiling (real vs real): median 0.928, 5th percentile 0.880 -> **material (instability replicates): True**
- reference, real vs G1 on the same programs: tau-b = 0.600 [0.524, 0.676]; discordant 20.0%; material: True
- G1 vs G2 orderings: tau-b = 0.543
- split-half ceiling within G2 programs: median 0.870, 5th percentile 0.779

**H4: ranking instability replicates under both prompts.**