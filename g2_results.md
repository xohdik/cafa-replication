# G2 results (PREREG_G2.md; scores in points, 95% percentile intervals unadjusted, Holm within model over the seven terms)

## DeepSeek-Coder-6.7B  (n = 1525 programs with all eight cells)

Identity check: 0.998 of 3083 shared cells identical between the confirmation file and the rerun.

Cell means (points), conditions in order 1,3,5,7 for real and 2,4,6,8 for generators: real 29.6, 29.7, 27.0, 26.5 | G1 13.4, 13.7, 23.1, 23.0 | G2 8.3, 8.4, 8.9, 8.6

| term | G1 est | G1 Holm p | G2 est | G2 95% interval | G2 p | G2 Holm p |
|---|---|---|---|---|---|---|
| I | +3.28 | 0.001 | -1.26 | [-2.03, -0.48] | 0.0014 | 0.007 |
| A | -0.03 | 1.000 | -0.15 | [-0.34, +0.03] | 0.1504 | 0.451 |
| S | -9.87 | 0.001 | -19.62 | [-21.95, -17.30] | 0.0002 | 0.001 |
| IA | -0.46 | 0.241 | -0.49 | [-0.89, -0.10] | 0.0166 | 0.066 |
| IS | +12.39 | 0.001 | +3.31 | [+1.77, +4.89] | 0.0002 | 0.001 |
| AS | +0.26 | 0.961 | +0.03 | [-0.33, +0.43] | 0.9365 | 1.000 |
| IAS | +0.26 | 1.000 | +0.20 | [-0.59, +0.98] | 0.6841 | 1.000 |

| simple effect | G1 | G2 |
|---|---|---|
| I / real | -2.92 [-4.39, -1.48] | -2.92 [-4.39, -1.48] |
| I / synth | +9.48 [+7.57, +11.44] | +0.39 [-0.16, +0.98] |
| S / orig-names | -16.07 [-18.75, -13.38] | -21.28 [-23.77, -18.79] |
| S / obf-names | -3.67 [-6.43, -0.89] | -17.97 [-20.43, -15.57] |

## StarCoder2  (n = 1525 programs with all eight cells)

Identity check: 0.998 of 3083 shared cells identical between the confirmation file and the rerun.

Cell means (points), conditions in order 1,3,5,7 for real and 2,4,6,8 for generators: real 23.5, 23.7, 22.6, 22.4 | G1 13.0, 15.3, 18.7, 18.0 | G2 7.9, 7.9, 8.0, 7.9

| term | G1 est | G1 Holm p | G2 est | G2 95% interval | G2 p | G2 Holm p |
|---|---|---|---|---|---|---|
| I | +1.54 | 0.002 | -0.52 | [-1.18, +0.11] | 0.1126 | 0.563 |
| A | +0.43 | 0.013 | -0.03 | [-0.23, +0.16] | 0.8039 | 1.000 |
| S | -6.82 | 0.001 | -15.15 | [-17.34, -12.90] | 0.0002 | 0.001 |
| IA | -1.70 | 0.001 | -0.20 | [-0.62, +0.23] | 0.4118 | 1.000 |
| IS | +5.31 | 0.001 | +1.18 | [-0.13, +2.52] | 0.0778 | 0.467 |
| AS | +0.85 | 0.013 | -0.07 | [-0.46, +0.33] | 0.7961 | 1.000 |
| IAS | -2.62 | 0.002 | +0.39 | [-0.46, +1.25] | 0.3990 | 1.000 |

| simple effect | G1 | G2 |
|---|---|---|
| I / real | -1.11 [-2.26, +0.00] | -1.11 [-2.26, +0.00] |
| I / synth | +4.20 [+2.85, +5.57] | +0.07 [-0.56, +0.69] |
| S / orig-names | -9.48 [-11.97, -6.95] | -15.74 [-18.07, -13.38] |
| S / obf-names | -4.16 [-6.66, -1.57] | -14.56 [-16.85, -12.23] |

## CodeLlama  (n = 1525 programs with all eight cells)

Identity check: 0.997 of 6166 shared cells identical between the confirmation file and the rerun.

Cell means (points), conditions in order 1,3,5,7 for real and 2,4,6,8 for generators: real 21.0, 21.2, 19.9, 20.3 | G1 17.8, 16.8, 17.7, 16.9 | G2 7.7, 7.7, 7.7, 7.7

| term | G1 est | G1 Holm p | G2 est | G2 95% interval | G2 p | G2 Holm p |
|---|---|---|---|---|---|---|
| I | -0.52 | 1.000 | -0.49 | [-1.15, +0.16] | 0.1550 | 0.713 |
| A | -0.33 | 0.200 | +0.16 | [-0.03, +0.38] | 0.1188 | 0.713 |
| S | -3.31 | 0.025 | -12.89 | [-15.00, -10.77] | 0.0002 | 0.001 |
| IA | +0.13 | 1.000 | +0.00 | [-0.33, +0.33] | 1.0000 | 1.000 |
| IS | +0.98 | 1.000 | +1.05 | [-0.26, +2.36] | 0.1284 | 0.713 |
| AS | -1.25 | 0.001 | -0.26 | [-0.66, +0.13] | 0.2026 | 0.713 |
| IAS | +0.13 | 1.000 | -0.13 | [-0.79, +0.52] | 0.7763 | 1.000 |

| simple effect | G1 | G2 |
|---|---|---|
| I / real | -1.02 [-2.20, +0.16] | -1.02 [-2.20, +0.16] |
| I / synth | -0.03 [-1.51, +1.44] | +0.03 [-0.56, +0.62] |
| S / orig-names | -3.80 [-6.30, -1.34] | -13.41 [-15.64, -11.15] |
| S / obf-names | -2.82 [-5.25, -0.43] | -12.36 [-14.56, -10.20] |

## Qwen2.5-Coder-7B  (n = 1525 programs with all eight cells)

Identity check: 0.999 of 6166 shared cells identical between the confirmation file and the rerun.

Cell means (points), conditions in order 1,3,5,7 for real and 2,4,6,8 for generators: real 28.6, 28.4, 26.1, 26.2 | G1 29.7, 29.8, 26.0, 25.8 | G2 10.2, 10.4, 10.2, 10.4

| term | G1 est | G1 Holm p | G2 est | G2 95% interval | G2 p | G2 Holm p |
|---|---|---|---|---|---|---|
| I | -3.07 | 0.001 | -1.16 | [-1.95, -0.38] | 0.0044 | 0.022 |
| A | -0.05 | 1.000 | +0.05 | [-0.18, +0.28] | 0.7243 | 1.000 |
| S | +0.51 | 1.000 | -17.03 | [-19.36, -14.66] | 0.0002 | 0.001 |
| IA | +0.03 | 1.000 | +0.16 | [-0.23, +0.59] | 0.4878 | 1.000 |
| IS | -1.48 | 0.936 | +2.33 | [+0.75, +3.87] | 0.0028 | 0.017 |
| AS | -0.03 | 1.000 | +0.16 | [-0.30, +0.62] | 0.5243 | 1.000 |
| IAS | -0.59 | 0.936 | -0.33 | [-1.11, +0.46] | 0.4738 | 1.000 |

| simple effect | G1 | G2 |
|---|---|---|
| I / real | -2.33 [-3.74, -0.92] | -2.33 [-3.74, -0.92] |
| I / synth | -3.80 [-5.21, -2.43] | +0.00 [-0.69, +0.69] |
| S / orig-names | +1.25 [-1.48, +3.97] | -18.20 [-20.66, -15.70] |
| S / obf-names | -0.23 [-2.95, +2.52] | -15.87 [-18.30, -13.44] |

## Qwen2.5-Coder-14B  (n = 1525 programs with all eight cells)

Identity check: 0.996 of 6166 shared cells identical between the confirmation file and the rerun.

Cell means (points), conditions in order 1,3,5,7 for real and 2,4,6,8 for generators: real 34.2, 34.0, 31.2, 31.7 | G1 37.5, 37.6, 34.5, 34.5 | G2 12.5, 12.1, 12.5, 12.6

| term | G1 est | G1 Holm p | G2 est | G2 95% interval | G2 p | G2 Holm p |
|---|---|---|---|---|---|---|
| I | -2.89 | 0.001 | -1.21 | [-2.16, -0.28] | 0.0130 | 0.065 |
| A | +0.10 | 1.000 | +0.00 | [-0.30, +0.31] | 1.0000 | 1.000 |
| S | +3.25 | 0.091 | -20.36 | [-22.66, -18.02] | 0.0002 | 0.001 |
| IA | +0.26 | 1.000 | +0.52 | [+0.03, +1.05] | 0.0488 | 0.195 |
| IS | -0.39 | 1.000 | +2.95 | [+1.08, +4.79] | 0.0022 | 0.013 |
| AS | -0.07 | 1.000 | -0.26 | [-0.89, +0.36] | 0.4364 | 1.000 |
| IAS | -0.79 | 0.753 | -0.26 | [-1.25, +0.72] | 0.6783 | 1.000 |

| simple effect | G1 | G2 |
|---|---|---|
| I / real | -2.69 [-4.36, -0.98] | -2.69 [-4.36, -0.98] |
| I / synth | -3.08 [-4.39, -1.80] | +0.26 [-0.56, +1.08] |
| S / orig-names | +3.44 [+0.59, +6.26] | -21.84 [-24.33, -19.31] |
| S / obf-names | +3.05 [+0.26, +5.84] | -18.89 [-21.38, -16.33] |

# H1 (direction replicates: DeepSeek-Coder and StarCoder2, identifiers x source under G2 positive with Holm p < 0.05)
- DeepSeek-Coder-6.7B: IS = +3.31 [+1.77, +4.89], Holm p = 0.001 -> satisfied
- StarCoder2: IS = +1.18 [-0.13, +2.52], Holm p = 0.467 -> not satisfied
**H1: partly replicated**

# H2 (generator dependence: G2 minus G1, paired by program; Holm over 5 models x 2 quantities; dependent if |difference| >= 3 points and Holm p < 0.05)
| model | quantity | G2 - G1 | 95% interval | p | Holm p | generator-dependent |
|---|---|---|---|---|---|---|
| DeepSeek-Coder-6.7B | S / orig-names | -5.21 | [-7.38, -3.15] | 0.0002 | 0.002 | YES |
| DeepSeek-Coder-6.7B | IS | -9.08 | [-11.11, -7.08] | 0.0002 | 0.002 | YES |
| StarCoder2 | S / orig-names | -6.26 | [-8.03, -4.52] | 0.0002 | 0.002 | YES |
| StarCoder2 | IS | -4.13 | [-5.67, -2.62] | 0.0002 | 0.002 | YES |
| CodeLlama | S / orig-names | -9.61 | [-11.51, -7.70] | 0.0002 | 0.002 | YES |
| CodeLlama | IS | +0.07 | [-1.54, +1.67] | 0.9413 | 0.941 | no |
| Qwen2.5-Coder-7B | S / orig-names | -19.44 | [-21.74, -17.21] | 0.0002 | 0.002 | YES |
| Qwen2.5-Coder-7B | IS | +3.80 | [+2.26, +5.41] | 0.0002 | 0.002 | YES |
| Qwen2.5-Coder-14B | S / orig-names | -25.28 | [-27.64, -22.95] | 0.0002 | 0.002 | YES |
| Qwen2.5-Coder-14B | IS | +3.34 | [+1.87, +4.85] | 0.0002 | 0.002 | YES |

# H3 (prompt dependence). Per model, with statement order original: S(prompt) = mean(c2,c6) - mean(c1,c5); SP = S(no demonstration) - S(original prompt); IS(prompt) = (c6-c2) - (c5-c1); ISP = IS(none) - IS(orig).
| model | n | G1 SP | G2 SP [95%] | G2 SP Holm p (over models) | same sign | G1 ISP | G2 ISP [95%] |
|---|---|---|---|---|---|---|---|
| DeepSeek-Coder-6.7B | 1525 | +11.44 | +5.44 [+4.07, +6.82] | 0.001 | yes | -9.51 | -0.66 [-2.89, +1.57] |
| StarCoder2 | 1525 | +6.66 | +6.33 [+4.85, +7.84] | 0.001 | yes | +6.49 | +0.20 [-1.64, +1.97] |
| CodeLlama | 1525 | +9.57 | +5.25 [+3.77, +6.75] | 0.001 | yes | +2.62 | +1.05 [-0.66, +2.75] |
| Qwen2.5-Coder-7B | 1525 | -7.64 | +1.84 [+0.56, +3.11] | 0.007 | no | +5.57 | -1.44 [-3.34, +0.59] |
| Qwen2.5-Coder-14B | 1525 | -4.72 | +5.08 [+3.57, +6.62] | 0.001 | no | -5.51 | +0.33 [-1.90, +2.62] |

**H3: 3 of 5 models satisfy it (needs at least 4 of 5): does not hold**

(Holm family for the H3 p-values is the five models' G2 SP values; PREREG_G2.md did not name it, so this choice is logged in DEVIATIONS.md.)