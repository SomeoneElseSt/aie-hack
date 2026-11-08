# SubQ gate on Martian Code Review Bench (strict, Opus 4.5 judge, diff-only context)

| tool | setting | thr | P | R | F1 | kept/total |
|---|---|---|---|---|---|---|
| greptile-v4-1 | ungated | - | 0.49 | 0.54 | 0.514 | 167/167 |
| greptile-v4-1 | gated, best thr (in-sample) | 0.65 | 0.58 | 0.50 | 0.535 | 127/167 |
| greptile-v4-1 | held-out A->B: ungated vs gated | 0.65 | 0.51→0.54 | 0.55→0.49 | 0.526→0.514 | 71/86 |
| greptile-v4-1 | held-out B->A: ungated vs gated | 0.05 | 0.47→0.47 | 0.53→0.53 | 0.500→0.500 | 81/81 |
| claude-code | ungated | - | 0.44 | 0.50 | 0.471 | 172/172 |
| claude-code | gated, best thr (in-sample) | 0.60 | 0.56 | 0.45 | 0.502 | 122/172 |
| claude-code | held-out A->B: ungated vs gated | 0.25 | 0.44→0.48 | 0.51→0.48 | 0.468→0.479 | 80/92 |
| claude-code | held-out B->A: ungated vs gated | 0.65 | 0.45→0.52 | 0.50→0.42 | 0.475→0.467 | 58/80 |
| coderabbit | ungated | - | 0.31 | 0.63 | 0.414 | 297/297 |
| coderabbit | gated, best thr (in-sample) | 0.75 | 0.56 | 0.55 | 0.556 | 145/297 |
| coderabbit | held-out A->B: ungated vs gated | 0.75 | 0.34→0.57 | 0.60→0.49 | 0.433→0.529 | 66/136 |
| coderabbit | held-out B->A: ungated vs gated | 0.55 | 0.28→0.45 | 0.65→0.62 | 0.396→0.519 | 98/161 |

SubQ calls ok=150 errors=0
