# Compare `v1-sonnet-test-k3` (baseline) -> `v1-sonnet-test-k3-o3` (candidate)

Paired cluster bootstrap over 43 common cases (10000 resamples), strict scoring. Delta = candidate - baseline. MDE = half-width of the delta CI: a delta inside it is reported as 'no detectable change'.

| metric | baseline | candidate | delta [95% CI] | p | MDE | verdict |
|---|---|---|---|---|---|---|
| recall | 0.857 [0.758, 0.946] | 0.841 [0.735, 0.932] | -0.016 [-0.081, 0.028] | 0.712 | 0.054 | no detectable change |
| recall_high | 0.901 [0.793, 1.000] | 0.864 [0.741, 0.970] | -0.037 [-0.135, 0.026] | 0.482 | 0.081 | no detectable change |
| precision | 0.561 [0.468, 0.668] | 0.568 [0.463, 0.687] | 0.007 [-0.058, 0.066] | 0.804 | 0.062 | no detectable change |
| precision_high | 0.964 [0.911, 1.000] | 0.974 [0.937, 1.000] | 0.011 [-0.032, 0.048] | 0.772 | 0.040 | no detectable change |
| f1 | 0.678 [0.594, 0.761] | 0.677 [0.580, 0.771] | -0.000 [-0.064, 0.051] | 0.959 | 0.057 | no detectable change |
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 | 0.000 | no detectable change |
| cost_usd_per_review | 0.0141 | 0.0070 | -0.007 [-0.008, -0.006] | 0.000 | 0.001 | improved |

## Gated slices

| slice | metric | delta [95% CI] | cases | verdict |
|---|---|---|---|---|
| kind:clean | recall | n/a [n/a, n/a] | 8 | n/a |
| kind:clean | recall_high | n/a [n/a, n/a] | 8 | n/a |
| kind:clean | precision | 0.000 [0.000, 0.000] | 8 | no detectable change |
| kind:clean | clean_false_alarm_rate | 0.000 [0.000, 0.000] | 8 | no detectable change |
| kind:real | recall | 0.000 [0.000, 0.000] | 6 | no detectable change |
| kind:real | recall_high | 0.000 [0.000, 0.000] | 6 | no detectable change |
| kind:real | precision | 0.036 [0.000, 0.091] | 6 | no detectable change |
| kind:real | clean_false_alarm_rate | n/a [n/a, n/a] | 6 | n/a |
| kind:seeded | recall | -0.019 [-0.095, 0.034] | 29 | no detectable change |
| kind:seeded | recall_high | -0.038 [-0.139, 0.026] | 29 | no detectable change |
| kind:seeded | precision | -0.005 [-0.076, 0.060] | 29 | no detectable change |
| kind:seeded | clean_false_alarm_rate | n/a [n/a, n/a] | 29 | n/a |
| category_group:api_contract | recall | 0.000 [0.000, 0.000] | 6 | no detectable change |
| category_group:error_handling | recall | 0.095 [0.000, 0.148] | 5 | improved |
| category_group:logic | recall | -0.033 [-0.111, 0.000] | 8 | no detectable change |
| category_group:performance | recall | -0.167 [-0.500, 0.000] | 6 | no detectable change |
| category_group:security | recall | 0.000 [0.000, 0.000] | 5 | no detectable change |
| category_group:state | recall | 0.000 [0.000, 0.000] | 6 | no detectable change |

## Per-bug detection (majority over k)

Exact McNemar over 42 bugs: 1 gained, 1 lost, p = 1.000.

| case | bug | severity | category | change | baseline | candidate |
|---|---|---|---|---|---|---|
| seeded-error-06 | b2 | high | error_handling | gained | 0.33 | 0.67 |
| seeded-perf-08 | b1 | high | performance | lost | 1.00 | 0.00 |
