# Compare `v1-sonnet-test-k3` (baseline) -> `v1-haiku-test-k3` (candidate)

Paired cluster bootstrap over 43 common cases (10000 resamples), strict scoring. Delta = candidate - baseline. MDE = half-width of the delta CI: a delta inside it is reported as 'no detectable change'.

| metric | baseline | candidate | delta [95% CI] | p | MDE | verdict |
|---|---|---|---|---|---|---|
| recall | 0.857 [0.758, 0.946] | 0.810 [0.689, 0.921] | -0.048 [-0.162, 0.056] | 0.441 | 0.109 | no detectable change |
| recall_high | 0.901 [0.793, 1.000] | 0.840 [0.690, 0.971] | -0.062 [-0.205, 0.053] | 0.525 | 0.129 | no detectable change |
| precision | 0.561 [0.468, 0.668] | 0.625 [0.509, 0.750] | 0.064 [-0.049, 0.178] | 0.271 | 0.114 | no detectable change |
| precision_high | 0.964 [0.911, 1.000] | 0.967 [0.915, 1.000] | 0.003 [-0.066, 0.071] | 0.906 | 0.069 | no detectable change |
| f1 | 0.678 [0.594, 0.761] | 0.704 [0.600, 0.802] | 0.027 [-0.083, 0.125] | 0.600 | 0.104 | no detectable change |
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 | 0.000 | no detectable change |
| cost_usd_per_review | 0.0141 | 0.0006 | -0.014 [-0.015, -0.012] | 0.000 | 0.002 | improved |

## Gated slices

| slice | metric | delta [95% CI] | cases | verdict |
|---|---|---|---|---|
| kind:clean | recall | n/a [n/a, n/a] | 8 | n/a |
| kind:clean | recall_high | n/a [n/a, n/a] | 8 | n/a |
| kind:clean | precision | 0.000 [0.000, 0.000] | 8 | no detectable change |
| kind:clean | clean_false_alarm_rate | 0.000 [0.000, 0.000] | 8 | no detectable change |
| kind:real | recall | -0.048 [-0.444, 0.389] | 6 | no detectable change |
| kind:real | recall_high | -0.667 [-0.667, -0.667] | 6 | regressed |
| kind:real | precision | -0.012 [-0.200, 0.098] | 6 | no detectable change |
| kind:real | clean_false_alarm_rate | n/a [n/a, n/a] | 6 | n/a |
| kind:seeded | recall | -0.048 [-0.162, 0.038] | 29 | no detectable change |
| kind:seeded | recall_high | -0.038 [-0.191, 0.067] | 29 | no detectable change |
| kind:seeded | precision | 0.106 [-0.028, 0.238] | 29 | no detectable change |
| kind:seeded | clean_false_alarm_rate | n/a [n/a, n/a] | 29 | n/a |
| category_group:api_contract | recall | 0.143 [0.000, 0.500] | 6 | no detectable change |
| category_group:error_handling | recall | 0.095 [0.000, 0.250] | 5 | no detectable change |
| category_group:logic | recall | -0.233 [-0.515, 0.000] | 8 | no detectable change |
| category_group:performance | recall | -0.111 [-0.333, 0.000] | 6 | no detectable change |
| category_group:security | recall | 0.000 [0.000, 0.000] | 5 | no detectable change |
| category_group:state | recall | -0.111 [-0.333, 0.000] | 6 | no detectable change |

## Per-bug detection (majority over k)

Exact McNemar over 42 bugs: 2 gained, 5 lost, p = 0.453.

| case | bug | severity | category | change | baseline | candidate |
|---|---|---|---|---|---|---|
| real-03 | b1 | medium | logic | lost | 0.67 | 0.00 |
| real-05 | b1 | medium | api_contract | gained | 0.00 | 1.00 |
| real-06 | b1 | high | concurrency | lost | 1.00 | 0.33 |
| seeded-error-06 | b2 | high | error_handling | gained | 0.33 | 1.00 |
| seeded-logic-07 | b1 | high | logic | lost | 1.00 | 0.00 |
| seeded-logic-07 | b2 | high | logic | lost | 1.00 | 0.33 |
| seeded-perf-09 | b1 | medium | performance | lost | 1.00 | 0.33 |
