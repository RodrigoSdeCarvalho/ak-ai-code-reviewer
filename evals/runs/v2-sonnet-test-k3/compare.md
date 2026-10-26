# Compare `v1-sonnet-test-k3` (baseline) -> `v2-sonnet-test-k3` (candidate)

Paired cluster bootstrap over 43 common cases (10000 resamples), strict scoring. Delta = candidate - baseline. MDE = half-width of the delta CI: a delta inside it is reported as 'no detectable change'.

| metric | baseline | candidate | delta [95% CI] | p | MDE | verdict |
|---|---|---|---|---|---|---|
| recall | 0.857 [0.758, 0.946] | 0.857 [0.758, 0.946] | 0.000 [0.000, 0.000] | 1.000 | 0.000 | no detectable change |
| recall_high | 0.901 [0.793, 1.000] | 0.901 [0.793, 1.000] | 0.000 [0.000, 0.000] | 1.000 | 0.000 | no detectable change |
| precision | 0.561 [0.468, 0.668] | 0.880 [0.805, 0.953] | 0.319 [0.225, 0.413] | 0.000 | 0.094 | improved |
| precision_high | 0.964 [0.911, 1.000] | 0.975 [0.923, 1.000] | 0.011 [0.000, 0.036] | 0.733 | 0.018 | no detectable change |
| f1 | 0.678 [0.594, 0.761] | 0.868 [0.800, 0.928] | 0.190 [0.128, 0.257] | 0.000 | 0.065 | improved |
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 | 0.000 | no detectable change |
| cost_usd_per_review | 0.0141 | 0.0141 | 0.000 [0.000, 0.000] | 1.000 | 0.000 | no detectable change |

## Gated slices

| slice | metric | delta [95% CI] | cases | verdict |
|---|---|---|---|---|
| kind:clean | recall | n/a [n/a, n/a] | 8 | n/a |
| kind:clean | recall_high | n/a [n/a, n/a] | 8 | n/a |
| kind:clean | precision | n/a [n/a, n/a] | 8 | n/a |
| kind:clean | clean_false_alarm_rate | 0.000 [0.000, 0.000] | 8 | no detectable change |
| kind:real | recall | 0.000 [0.000, 0.000] | 6 | no detectable change |
| kind:real | recall_high | 0.000 [0.000, 0.000] | 6 | no detectable change |
| kind:real | precision | 0.036 [0.000, 0.091] | 6 | no detectable change |
| kind:real | clean_false_alarm_rate | n/a [n/a, n/a] | 6 | n/a |
| kind:seeded | recall | 0.000 [0.000, 0.000] | 29 | no detectable change |
| kind:seeded | recall_high | 0.000 [0.000, 0.000] | 29 | no detectable change |
| kind:seeded | precision | 0.324 [0.232, 0.406] | 29 | improved |
| kind:seeded | clean_false_alarm_rate | n/a [n/a, n/a] | 29 | n/a |
| category_group:api_contract | recall | 0.000 [0.000, 0.000] | 6 | no detectable change |
| category_group:error_handling | recall | 0.000 [0.000, 0.000] | 5 | no detectable change |
| category_group:logic | recall | 0.000 [0.000, 0.000] | 8 | no detectable change |
| category_group:performance | recall | 0.000 [0.000, 0.000] | 6 | no detectable change |
| category_group:security | recall | 0.000 [0.000, 0.000] | 5 | no detectable change |
| category_group:state | recall | 0.000 [0.000, 0.000] | 6 | no detectable change |

## Per-bug detection (majority over k)

Exact McNemar over 42 bugs: 0 gained, 0 lost, p = 1.000.

No flips.
