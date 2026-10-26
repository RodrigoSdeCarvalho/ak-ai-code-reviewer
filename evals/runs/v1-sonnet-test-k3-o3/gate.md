# Gate: **PASS** (exit 0)

Run `v1-sonnet-test-k3-o3` vs baseline `v1-sonnet-test-k3`; regression basis: paired; absolute bars acceptance: PENDING.

| check | status | blocking | value | bar | provenance | detail |
|---|---|---|---|---|---|---|
| completeness.run_complete | PASS | yes | {'incomplete': False, 'missing': 0} | no missing samples | design §7 |  |
| completeness.hard_errors | PASS | yes | 0 | <= 0 | design §7 |  |
| completeness.soft_errors | PASS | yes | 0.0 | <= 0.02 | design §7 | 0 truncated/refused of 129 |
| completeness.judge | PASS | yes | {'missing': 0, 'error_rate': 0.0} | 0 missing, error rate <= 0.02 | design §7 |  |
| absolute.recall_high | PASS | no | 0.8642 | >= 0.75 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.901 [0.793, 1.000]; bar = CI lower bound rounded down | advisory: acceptance PENDING |
| absolute.clean_false_alarm_rate | PASS | no | 0.0 | <= 0.15 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.000 over 8 clean cases x 3; bar allows one case alarming in every sample (0.125), not two | advisory: acceptance PENDING |
| absolute.precision | PASS | no | 0.5676 | >= 0.45 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.561 [0.468, 0.668]; bar = CI lower bound rounded down | advisory: acceptance PENDING |
| regression.recall | PASS | yes | -0.0159 | delta CI bad end not below -0.1 (non-inferiority) | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta -0.016 [-0.081, +0.028] over 43 cases |
| regression.recall_high | PASS | yes | -0.037 | delta CI bad end not below -0.15 (non-inferiority) | MEASURED A/A 2026-10-26: delta -0.037 [-0.135, +0.026] | paired delta -0.037 [-0.135, +0.026] over 43 cases |
| regression.precision | PASS | yes | 0.0066 | delta CI bad end not below -0.07 (non-inferiority) | MEASURED A/A 2026-10-26: delta +0.007 [-0.058, +0.066] | paired delta +0.007 [-0.058, +0.066] over 43 cases |
| regression.clean_false_alarm_rate | PASS | yes | 0.0 | delta CI bad end not above +0.15 (non-inferiority) | DEFAULT kept: A/A had 0 alarms in both runs (no spread to measure); 0.125 = one clean case alarming in every sample | paired delta +0.000 [+0.000, +0.000] over 43 cases |
| regression.kind:clean.precision | PASS | yes | 0.0 | delta CI not entirely below -0.07 | MEASURED A/A 2026-10-26: delta +0.007 [-0.058, +0.066] | paired delta +0.000 [+0.000, +0.000] over 8 cases |
| regression.kind:clean.clean_false_alarm_rate | PASS | yes | 0.0 | delta CI not entirely above +0.15 | DEFAULT kept: A/A had 0 alarms in both runs (no spread to measure); 0.125 = one clean case alarming in every sample | paired delta +0.000 [+0.000, +0.000] over 8 cases |
| regression.kind:real.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta +0.000 [+0.000, +0.000] over 6 cases |
| regression.kind:real.recall_high | INSUFFICIENT_DATA | yes | 0.0 | delta CI not entirely below -0.15 | MEASURED A/A 2026-10-26: delta -0.037 [-0.135, +0.026] | n=1 < 6 |
| regression.kind:real.precision | PASS | yes | 0.0357 | delta CI not entirely below -0.07 | MEASURED A/A 2026-10-26: delta +0.007 [-0.058, +0.066] | paired delta +0.036 [+0.000, +0.091] over 6 cases |
| regression.kind:seeded.recall | PASS | yes | -0.019 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta -0.019 [-0.095, +0.034] over 29 cases |
| regression.kind:seeded.recall_high | PASS | yes | -0.0385 | delta CI not entirely below -0.15 | MEASURED A/A 2026-10-26: delta -0.037 [-0.135, +0.026] | paired delta -0.038 [-0.139, +0.026] over 29 cases |
| regression.kind:seeded.precision | PASS | yes | -0.0046 | delta CI not entirely below -0.07 | MEASURED A/A 2026-10-26: delta +0.007 [-0.058, +0.066] | paired delta -0.005 [-0.076, +0.060] over 29 cases |
| regression.category_group:api_contract.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta +0.000 [+0.000, +0.000] over 6 cases |
| regression.category_group:error_handling.recall | PASS | yes | 0.0952 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta +0.095 [+0.000, +0.148] over 5 cases |
| regression.category_group:logic.recall | PASS | yes | -0.0333 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta -0.033 [-0.111, +0.000] over 8 cases |
| regression.category_group:performance.recall | PASS | yes | -0.1667 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta -0.167 [-0.500, +0.000] over 6 cases |
| regression.category_group:security.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta +0.000 [+0.000, +0.000] over 5 cases |
| regression.category_group:state.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | MEASURED A/A 2026-10-26: delta -0.016 [-0.081, +0.028] | paired delta +0.000 [+0.000, +0.000] over 6 cases |
| newly_missed_critical | PASS | yes | 1 | <= 1 critical/high bugs with baseline rate >= 0.66 and candidate rate <= 0.0 | MEASURED A/A 2026-10-26: an identical config re-sampled lost 1 high bug (seeded-perf-08/b1, 3/3 -> 0/3) | seeded-perf-08/b1 |
| cost.per_review | PASS | no | 0.495 | <= 1.5x baseline | design §7 | 0.006969 vs 0.01408 |
| latency.p95 | SKIPPED | no |  | <= 1.5x baseline | design §7 | not measured in baseline or candidate |
