# R4 results (PREREG_R4.md; points; unadjusted 95% program-level percentile intervals; Holm over five models for I|real(mean))

| model | programs (dropped) | acc. cond. 1: single / mean / strict | I given real: single | I given real: mean (primary) | I given real: strict | mean - single | Holm p (mean) | single correct but not all (share) |
|---|---|---|---|---|---|---|---|---|
| DeepSeek-Coder-6.7B | 1423 (2) | 31.0 / 21.6 / 5.6 | -2.67 [-4.29, -1.12] | -1.09 [-1.92, -0.27] | -0.49 [-1.26, +0.28] | +1.58 [+0.40, +2.80] | 0.020 | 25.4% |
| StarCoder2 | 1423 (2) | 24.3 / 17.8 / 3.9 | -0.70 [-1.97, +0.49] | -1.03 [-1.72, -0.35] | -0.77 [-1.41, -0.21] | -0.33 [-1.31, +0.68] | 0.015 | 20.4% |
| CodeLlama | 1423 (2) | 22.1 / 16.6 / 3.2 | -0.98 [-2.25, +0.28] | -0.66 [-1.34, +0.01] | -0.49 [-1.12, +0.07] | +0.33 [-0.70, +1.35] | 0.056 | 18.8% |
| Qwen2.5-Coder-7B | 1423 (2) | 29.7 / 23.1 / 7.0 | -2.60 [-4.15, -1.05] | -1.49 [-2.35, -0.62] | -0.70 [-1.55, +0.14] | +1.11 [-0.13, +2.37] | 0.003 | 22.7% |
| Qwen2.5-Coder-14B | 1423 (2) | 35.8 / 28.8 / 11.1 | -3.16 [-4.99, -1.41] | -1.83 [-2.80, -0.84] | -1.12 [-2.32, +0.07] | +1.34 [-0.07, +2.74] | 0.001 | 24.7% |

**Direction (I|real(mean) negative in all five models): holds (5 of 5). Size (|mean - single| <= 1.5 points in every model): does not hold (4 of 5).**
Reading fixed in PREREG_R4.md: the sign holds; the multi-input estimate is reported as the estimate.