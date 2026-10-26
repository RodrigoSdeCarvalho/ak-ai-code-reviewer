# Eval run `v2-sonnet-test-k3`

|  |  |
|---|---|
| Config | v2-sonnet (backend anthropic, effort medium) |
| Model / prompt | claude-sonnet-5-5 / v1 (hash 308e4c19584c) |
| Dataset | v1.0.0 (hash 8ad094c9ed2b) |
| Split / cases / k | test / 43 / 3 |
| Cases by kind | clean 8, real 6, seeded 29 |
| Must-find bugs (high+) | 42 (27) |
| Mode | replay |
| Judge | claude-haiku-5-5 / same-defect-v2 |
| Location tolerance | ±3 lines |
| Created | 2026-10-26T18:32:43+00:00 (git d884bc89c6 (dirty)) |
| CIs | 95% cluster bootstrap over cases, 10000 resamples |

## Headline

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| recall | 0.857 [0.758, 0.946] | 0.865 [0.770, 0.949] | 42 |
| recall_high | 0.901 [0.793, 1.000] | 0.901 [0.793, 1.000] | 27 |
| precision | 0.880 [0.805, 0.953] | 0.974 [0.934, 1.000] | 43 |
| precision_high | 0.975 [0.923, 1.000] | 0.975 [0.923, 1.000] | 43 |
| f1 | 0.868 [0.800, 0.928] | 0.916 [0.856, 0.968] | 42 |
| fp_per_case | 0.116 [0.039, 0.202] | 0.023 [0.000, 0.062] | 43 |

Strict = location candidate + judge `same`; location-only ignores the judge. Strict pairs with a judge error: 0, without a judgment: 0 (both count as not matched).

## Clean cases (false alarms)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 8 |
| clean_fp_per_case | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 8 |

`clean_false_alarm_rate` = share of clean cases with at least one finding of severity high or critical.

## Consistency over k samples

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| pass_all_k | 0.833 [0.723, 0.930] | 0.833 [0.723, 0.930] | 42 |
| pass_any_k | 0.881 [0.780, 0.973] | 0.905 [0.814, 0.977] | 42 |
| duplicate_rate | 0.000 [0.000, 0.000] | 0.089 [0.018, 0.164] | 43 |

pass^k = bug detected in every scorable sample; pass@k = in at least one.

## Severity / category agreement (on true-positive pairs)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| severity_exact | 0.593 [0.424, 0.747] | 0.596 [0.431, 0.750] | 108 |
| severity_within1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 108 |
| category_accuracy | 0.787 [0.658, 0.910] | 0.780 [0.651, 0.902] | 108 |
| localization_mae | 0.19 [0.01, 0.54] | 0.18 [0.01, 0.53] | 108 |

## Slices

Slices with fewer than 6 units are marked INSUFFICIENT_DATA and cannot fail the gate.

| slice | value | cases | bugs | recall | precision | clean FA rate | recall (loc) | note |
|---|---|---|---|---|---|---|---|---|
| kind | clean | 8 | 0 | n/a | n/a | 0.000 [0.000, 0.000] | n/a |  |
| kind | real | 6 | 7 | 0.810 [0.444, 1.000] | 0.849 [0.625, 1.000] | n/a | 0.810 [0.444, 1.000] |  |
| kind | seeded | 29 | 35 | 0.867 [0.761, 0.969] | 0.886 [0.809, 0.961] | n/a | 0.876 [0.781, 0.970] |  |
| size_bucket | L | 9 | 11 | 0.848 [0.625, 1.000] | 0.906 [0.800, 1.000] | 0.000 [0.000, 0.000] | 0.848 [0.625, 1.000] |  |
| size_bucket | M | 20 | 19 | 0.895 [0.773, 1.000] | 0.866 [0.752, 0.981] | 0.000 [0.000, 0.000] | 0.895 [0.773, 1.000] |  |
| size_bucket | S | 14 | 12 | 0.806 [0.556, 1.000] | 0.881 [0.713, 1.000] | 0.000 [0.000, 0.000] | 0.833 [0.611, 1.000] |  |
| seeded_size_bucket | L | 8 | 11 | 0.848 [0.633, 1.000] | 0.906 [0.800, 1.000] | n/a | 0.848 [0.633, 1.000] |  |
| seeded_size_bucket | M | 16 | 19 | 0.895 [0.773, 1.000] | 0.866 [0.750, 0.981] | n/a | 0.895 [0.773, 1.000] |  |
| seeded_size_bucket | S | 5 | 5 | 0.800 [0.400, 1.000] | 0.933 [0.800, 1.000] | n/a | 0.867 [0.600, 1.000] | INSUFFICIENT_DATA |
| split | test | 43 | 42 | 0.857 [0.758, 0.946] | 0.880 [0.805, 0.953] | 0.000 [0.000, 0.000] | 0.865 [0.770, 0.949] |  |

| slice | value | bugs | recall | pass^k | recall (loc) | note |
|---|---|---|---|---|---|---|
| category_group | api_contract | 7 | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] |  |
| category_group | error_handling | 7 | 0.762 [0.593, 1.000] | 0.714 [0.556, 1.000] | 0.762 [0.593, 1.000] |  |
| category_group | logic | 10 | 0.967 [0.889, 1.000] | 0.900 [0.667, 1.000] | 0.967 [0.889, 1.000] |  |
| category_group | performance | 6 | 0.833 [0.500, 1.000] | 0.833 [0.500, 1.000] | 0.889 [0.667, 1.000] |  |
| category_group | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| category_group | state | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| category | api_contract | 7 | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] |  |
| category | concurrency | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | error_handling | 7 | 0.762 [0.593, 1.000] | 0.714 [0.556, 1.000] | 0.762 [0.593, 1.000] |  |
| category | logic | 10 | 0.967 [0.889, 1.000] | 0.900 [0.667, 1.000] | 0.967 [0.889, 1.000] |  |
| category | performance | 6 | 0.833 [0.500, 1.000] | 0.833 [0.500, 1.000] | 0.889 [0.667, 1.000] |  |
| category | resource | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | critical | 8 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | high | 19 | 0.860 [0.714, 1.000] | 0.842 [0.682, 1.000] | 0.860 [0.714, 1.000] |  |
| severity | medium | 15 | 0.778 [0.548, 0.958] | 0.733 [0.500, 0.938] | 0.800 [0.595, 0.961] |  |
| tag | library_knowledge | 1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| tag | unshown_context | 4 | 0.500 [0.000, 1.000] | 0.500 [0.000, 1.000] | 0.500 [0.000, 1.000] | INSUFFICIENT_DATA |
| tag | untagged | 38 | 0.895 [0.800, 0.974] | 0.868 [0.757, 0.971] | 0.904 [0.816, 0.976] |  |

## Location tolerance sensitivity (point values)

| tol | recall | precision | f1 | recall (loc) | precision (loc) | judge err / missing |
|---|---|---|---|---|---|---|
| ±0 | 0.849 | 0.872 | 0.860 | 0.857 | 0.917 | 0 / 0 |
| ±3 (scored) | 0.857 | 0.880 | 0.868 | 0.865 | 0.974 | 0 / 0 |
| ±5 | 0.873 | 0.896 | 0.884 | 0.881 | 0.991 | 0 / 0 |
| ±10 | 0.873 | 0.896 | 0.884 | 0.881 | 1.000 | 0 / 0 |

## Serving outcomes

129 of 129 samples scorable (status `ok`). Other statuses are infra outcomes, excluded from quality metrics, never scored as 'no findings'.

| status | samples | share |
|---|---|---|
| ok | 129 | 1.000 |
| truncated | 0 | 0.000 |
| refused | 0 | 0.000 |
| schema_error | 0 | 0.000 |
| api_error | 0 | 0.000 |
| missing | 0 | 0.000 |

Findings on files outside the diff (dropped, counted): 0.

## Ops

|  |  |
|---|---|
| reviews | 129 |
| reviewer cost (USD) | 1.8159 |
| cost per review (USD) | 0.0141 |
| latency | p50 4125 ms, p95 7331 ms over 129 calls |
| tokens in / out | 583557 / 55794 |
| cache read / write | 324375 / 10380 |
| judge calls / errors | 132 / 0 |
| judge cost (USD) | 0.0210 |

## Missed bugs (strict detect rate < 1)

| case | bug | file:lines | severity | category | detect (strict) | detect (loc) |
|---|---|---|---|---|---|---|
| real-05 | b1 | src/click/_utils.py:15-21 | medium | api_contract | 0.00 | 0.00 |
| seeded-api-06 | b2 | expenses/policy.py:22-22 | high | api_contract | 0.00 | 0.00 |
| seeded-api-08 | b1 | fleet/registry.py:33-35 | high | api_contract | 0.00 | 0.00 |
| seeded-error-03 | b1 | billing/retry.py:55-55 | medium | error_handling | 0.00 | 0.00 |
| seeded-perf-05 | b1 | newsletter/campaign.py:78-81 | medium | performance | 0.00 | 0.33 |
| seeded-error-06 | b2 | auth/sessions.py:98-100 | high | error_handling | 0.33 | 0.33 |
| real-03 | b1 | pydantic/root_model.py:104-106 | medium | logic | 0.67 | 0.67 |

## False positives (strict)

| case | sample | file:line | severity | title | triage |
|---|---|---|---|---|---|
| real-08 | 0 | celery/worker/strategy.py:189 | medium | Task failure no longer recorded in result backend for invalid ETA | incorrect |
| real-08 | 1 | celery/worker/strategy.py:189 | medium | Failure no longer recorded in result backend for invalid ETA | nit |
| real-08 | 2 | celery/worker/strategy.py:189 | medium | Failure no longer recorded in result backend for invalid ETA | incorrect |
| seeded-error-04 | 2 | scheduler/runner.py:82 | medium | Unbounded exponent in backoff can raise OverflowError | valid_issue |
| seeded-error-06 | 1 | auth/sessions.py:104 | high | change_password swallows revocation failures, leaving old sessions alive | valid_issue |
| seeded-error-06 | 2 | auth/sessions.py:104 | high | change_password silently leaves sessions alive when revocation fails | valid_issue |
| seeded-logic-08 | 0 | blobstore/store.py:80 | medium | Metadata written before blob leaves inconsistent state on failure | valid_issue |
| seeded-logic-08 | 1 | blobstore/store.py:81 | medium | Metadata written before blob; failed blob write leaves inconsistent state | valid_issue |
| seeded-logic-08 | 2 | blobstore/store.py:82 | medium | Metadata written before blob, leaving inconsistent state on failure | valid_issue |
| seeded-perf-05 | 2 | newsletter/campaign.py:78 | medium | A single non-refusal send error aborts the whole campaign and the report is lost | valid_issue |
| seeded-security-04 | 2 | workspace/invites.py:100 | medium | Check-then-act on uses allows exceeding max_uses | nit |
| seeded-state-01 | 2 | inventory/service.py:93 | medium | Rollback only for InventoryError, not other exceptions | valid_issue |
| seeded-state-02 | 0 | storage/blobs.py:67 | medium | Failure after write leaves temp file behind | valid_issue |
| seeded-state-02 | 1 | storage/blobs.py:68 | medium | Temp file leaked if mkdir/replace fails | valid_issue |
| seeded-state-02 | 2 | storage/blobs.py:68 | medium | Temp file leaked if mkdir or os.replace fails | valid_issue |

FP triage (advisory, never changes the headline): incorrect 2, nit 2, valid_issue 11
