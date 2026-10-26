# Gate: **PASS** (exit 0)

Run `v2-sonnet-test-k3` vs baseline `v1-sonnet-test-k3`; regression basis: paired; absolute bars acceptance: PENDING.

| check | status | blocking | value | bar | provenance | detail |
|---|---|---|---|---|---|---|
| completeness.run_complete | PASS | yes | {'incomplete': False, 'missing': 0} | no missing samples | design §7 |  |
| completeness.hard_errors | PASS | yes | 0 | <= 0 | design §7 |  |
| completeness.soft_errors | PASS | yes | 0.0 | <= 0.02 | design §7 | 0 truncated/refused of 129 |
| completeness.judge | PASS | yes | {'missing': 0, 'error_rate': 0.0} | 0 missing, error rate <= 0.02 | design §7 |  |
| absolute.recall_high | PASS | no | 0.9012 | >= 0.75 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.901 [0.793, 1.000]; bar = CI lower bound rounded down | advisory: acceptance PENDING |
| absolute.clean_false_alarm_rate | PASS | no | 0.0 | <= 0.15 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.000 over 8 clean cases x 3; bar allows one case alarming in every sample (0.125), not two | advisory: acceptance PENDING |
| absolute.precision | PASS | no | 0.8804 | >= 0.45 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.561 [0.468, 0.668]; bar = CI lower bound rounded down | advisory: acceptance PENDING |
| regression.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 43 cases |
| regression.recall_high | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 43 cases |
| regression.precision | PASS | yes | 0.3194 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.319 [+0.225, +0.413] over 43 cases |
| regression.clean_false_alarm_rate | PASS | yes | 0.0 | delta CI not entirely above +0.15 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 43 cases |
| regression.kind:clean.clean_false_alarm_rate | PASS | yes | 0.0 | delta CI not entirely above +0.15 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 8 cases |
| regression.kind:real.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 6 cases |
| regression.kind:real.recall_high | INSUFFICIENT_DATA | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | n=1 < 6 |
| regression.kind:real.precision | PASS | yes | 0.0357 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.036 [+0.000, +0.091] over 6 cases |
| regression.kind:seeded.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 29 cases |
| regression.kind:seeded.recall_high | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 29 cases |
| regression.kind:seeded.precision | PASS | yes | 0.3242 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.324 [+0.232, +0.406] over 29 cases |
| regression.category_group:api_contract.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 6 cases |
| regression.category_group:error_handling.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 5 cases |
| regression.category_group:logic.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 8 cases |
| regression.category_group:performance.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 6 cases |
| regression.category_group:security.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 5 cases |
| regression.category_group:state.recall | PASS | yes | 0.0 | delta CI not entirely below -0.1 | DEFAULT — replace with measured noise floor | paired delta +0.000 [+0.000, +0.000] over 6 cases |
| newly_missed_critical | PASS | yes | 0 | 0 critical/high bugs with baseline rate >= 0.66 and candidate rate <= 0.0 | design §7 |  |
| cost.per_review | PASS | no | 1.0 | <= 1.5x baseline | design §7 | 0.01408 vs 0.01408 |
| latency.p95 | PASS | no | 1.0 | <= 1.5x baseline | design §7 | 7331 vs 7331 |
