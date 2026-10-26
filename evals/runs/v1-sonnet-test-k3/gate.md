# Gate: **PASS** (exit 0)

Run `v1-sonnet-test-k3` vs baseline `None`; regression basis: none; absolute bars acceptance: PENDING.

| check | status | blocking | value | bar | provenance | detail |
|---|---|---|---|---|---|---|
| completeness.run_complete | PASS | yes | {'incomplete': False, 'missing': 0} | no missing samples | design §7 |  |
| completeness.hard_errors | PASS | yes | 0 | <= 0 | design §7 |  |
| completeness.soft_errors | PASS | yes | 0.0 | <= 0.02 | design §7 | 0 truncated/refused of 129 |
| completeness.judge | PASS | yes | {'missing': 0, 'error_rate': 0.0} | 0 missing, error rate <= 0.02 | design §7 |  |
| absolute.recall_high | PASS | no | 0.9012 | >= 0.75 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.901 [0.793, 1.000]; bar = CI lower bound rounded down | advisory: acceptance PENDING |
| absolute.clean_false_alarm_rate | PASS | no | 0.0 | <= 0.15 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.000 over 8 clean cases x 3; bar allows one case alarming in every sample (0.125), not two | advisory: acceptance PENDING |
| absolute.precision | PASS | no | 0.561 | >= 0.45 | MEASURED 2026-10-26 on v1-sonnet-test-k3: 0.561 [0.468, 0.668]; bar = CI lower bound rounded down | advisory: acceptance PENDING |
| regression | SKIPPED | yes |  |  |  | no baseline promoted yet |
