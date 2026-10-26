# Eval run `v1-sonnet-test-k3`

|  |  |
|---|---|
| Config | v1-sonnet (backend anthropic, effort medium) |
| Model / prompt | claude-sonnet-5-5 / v1 (hash 308e4c19584c) |
| Dataset | v1.0.0 (hash 8ad094c9ed2b) |
| Split / cases / k | test / 43 / 3 |
| Cases by kind | clean 8, real 6, seeded 29 |
| Must-find bugs (high+) | 42 (27) |
| Mode | record |
| Judge | claude-haiku-5-5 / same-defect-v2 |
| Location tolerance | ±3 lines |
| Created | 2026-10-26T18:15:47+00:00 (git d884bc89c6 (dirty)) |
| CIs | 95% cluster bootstrap over cases, 10000 resamples |

## Headline

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| recall | 0.857 [0.758, 0.946] | 0.881 [0.789, 0.963] | 42 |
| recall_high | 0.901 [0.793, 1.000] | 0.901 [0.793, 1.000] | 27 |
| precision | 0.561 [0.468, 0.668] | 0.658 [0.546, 0.789] | 43 |
| precision_high | 0.964 [0.911, 1.000] | 0.975 [0.923, 1.000] | 43 |
| f1 | 0.678 [0.594, 0.761] | 0.753 [0.662, 0.842] | 42 |
| fp_per_case | 0.659 [0.426, 0.922] | 0.450 [0.240, 0.705] | 43 |

Strict = location candidate + judge `same`; location-only ignores the judge. Strict pairs with a judge error: 0, without a judgment: 0 (both count as not matched).

## Clean cases (false alarms)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 8 |
| clean_fp_per_case | 0.417 [0.000, 1.133] | 0.417 [0.000, 1.133] | 8 |

`clean_false_alarm_rate` = share of clean cases with at least one finding of severity high or critical.

## Consistency over k samples

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| pass_all_k | 0.833 [0.723, 0.930] | 0.857 [0.756, 0.951] | 42 |
| pass_any_k | 0.881 [0.780, 0.973] | 0.905 [0.814, 0.977] | 42 |
| duplicate_rate | 0.000 [0.000, 0.000] | 0.124 [0.057, 0.197] | 43 |

pass^k = bug detected in every scorable sample; pass@k = in at least one.

## Severity / category agreement (on true-positive pairs)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| severity_exact | 0.593 [0.424, 0.747] | 0.604 [0.440, 0.754] | 108 |
| severity_within1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 108 |
| category_accuracy | 0.787 [0.658, 0.910] | 0.766 [0.633, 0.892] | 108 |
| localization_mae | 0.19 [0.01, 0.54] | 0.18 [0.01, 0.52] | 108 |

## Slices

Slices with fewer than 6 units are marked INSUFFICIENT_DATA and cannot fail the gate.

| slice | value | cases | bugs | recall | precision | clean FA rate | recall (loc) | note |
|---|---|---|---|---|---|---|---|---|
| kind | clean | 8 | 0 | n/a | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | n/a |  |
| kind | real | 6 | 7 | 0.810 [0.444, 1.000] | 0.813 [0.611, 1.000] | n/a | 0.810 [0.444, 1.000] |  |
| kind | seeded | 29 | 35 | 0.867 [0.761, 0.969] | 0.562 [0.473, 0.677] | n/a | 0.895 [0.802, 0.979] |  |
| size_bucket | L | 9 | 11 | 0.848 [0.625, 1.000] | 0.464 [0.326, 0.661] | 0.000 [0.000, 0.000] | 0.848 [0.625, 1.000] |  |
| size_bucket | M | 20 | 19 | 0.895 [0.773, 1.000] | 0.539 [0.422, 0.679] | 0.000 [0.000, 0.000] | 0.895 [0.773, 1.000] |  |
| size_bucket | S | 14 | 12 | 0.806 [0.556, 1.000] | 0.789 [0.565, 1.000] | 0.000 [0.000, 0.000] | 0.889 [0.694, 1.000] |  |
| seeded_size_bucket | L | 8 | 11 | 0.848 [0.633, 1.000] | 0.483 [0.344, 0.700] | n/a | 0.848 [0.633, 1.000] |  |
| seeded_size_bucket | M | 16 | 19 | 0.895 [0.773, 1.000] | 0.582 [0.482, 0.712] | n/a | 0.895 [0.773, 1.000] |  |
| seeded_size_bucket | S | 5 | 5 | 0.800 [0.400, 1.000] | 0.756 [0.350, 1.000] | n/a | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| split | test | 43 | 42 | 0.857 [0.758, 0.946] | 0.561 [0.468, 0.668] | 0.000 [0.000, 0.000] | 0.881 [0.789, 0.963] |  |

| slice | value | bugs | recall | pass^k | recall (loc) | note |
|---|---|---|---|---|---|---|
| category_group | api_contract | 7 | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] |  |
| category_group | error_handling | 7 | 0.762 [0.593, 1.000] | 0.714 [0.556, 1.000] | 0.762 [0.593, 1.000] |  |
| category_group | logic | 10 | 0.967 [0.889, 1.000] | 0.900 [0.667, 1.000] | 0.967 [0.889, 1.000] |  |
| category_group | performance | 6 | 0.833 [0.500, 1.000] | 0.833 [0.500, 1.000] | 1.000 [1.000, 1.000] |  |
| category_group | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| category_group | state | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| category | api_contract | 7 | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] |  |
| category | concurrency | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | error_handling | 7 | 0.762 [0.593, 1.000] | 0.714 [0.556, 1.000] | 0.762 [0.593, 1.000] |  |
| category | logic | 10 | 0.967 [0.889, 1.000] | 0.900 [0.667, 1.000] | 0.967 [0.889, 1.000] |  |
| category | performance | 6 | 0.833 [0.500, 1.000] | 0.833 [0.500, 1.000] | 1.000 [1.000, 1.000] |  |
| category | resource | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | critical | 8 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | high | 19 | 0.860 [0.714, 1.000] | 0.842 [0.682, 1.000] | 0.860 [0.714, 1.000] |  |
| severity | medium | 15 | 0.778 [0.548, 0.958] | 0.733 [0.500, 0.938] | 0.844 [0.643, 1.000] |  |
| tag | library_knowledge | 1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| tag | unshown_context | 4 | 0.500 [0.000, 1.000] | 0.500 [0.000, 1.000] | 0.500 [0.000, 1.000] | INSUFFICIENT_DATA |
| tag | untagged | 38 | 0.895 [0.800, 0.974] | 0.868 [0.757, 0.971] | 0.921 [0.838, 0.991] |  |

## Location tolerance sensitivity (point values)

| tol | recall | precision | f1 | recall (loc) | precision (loc) | judge err / missing |
|---|---|---|---|---|---|---|
| ±0 | 0.849 | 0.556 | 0.671 | 0.873 | 0.593 | 0 / 0 |
| ±3 (scored) | 0.857 | 0.561 | 0.678 | 0.881 | 0.658 | 0 / 0 |
| ±5 | 0.873 | 0.571 | 0.690 | 0.897 | 0.686 | 0 / 0 |
| ±10 | 0.873 | 0.571 | 0.690 | 0.897 | 0.699 | 0 / 0 |

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
| judge calls / errors | 153 / 0 |
| judge cost (USD) | 0.0244 |

## Missed bugs (strict detect rate < 1)

| case | bug | file:lines | severity | category | detect (strict) | detect (loc) |
|---|---|---|---|---|---|---|
| real-05 | b1 | src/click/_utils.py:15-21 | medium | api_contract | 0.00 | 0.00 |
| seeded-api-06 | b2 | expenses/policy.py:22-22 | high | api_contract | 0.00 | 0.00 |
| seeded-api-08 | b1 | fleet/registry.py:33-35 | high | api_contract | 0.00 | 0.00 |
| seeded-error-03 | b1 | billing/retry.py:55-55 | medium | error_handling | 0.00 | 0.00 |
| seeded-perf-05 | b1 | newsletter/campaign.py:78-81 | medium | performance | 0.00 | 1.00 |
| seeded-error-06 | b2 | auth/sessions.py:98-100 | high | error_handling | 0.33 | 0.33 |
| real-03 | b1 | pydantic/root_model.py:104-106 | medium | logic | 0.67 | 0.67 |

## False positives (strict)

| case | sample | file:line | severity | title | triage |
|---|---|---|---|---|---|
| clean-04 | 0 | sessions/store.py:103 | medium | Bare except with unguarded unlink can mask the original error | nit |
| clean-04 | 0 | sessions/store.py:42 | medium | Expired sessions are no longer removed on access | nit |
| clean-04 | 1 | sessions/store.py:103 | medium | Bare except cleanup can mask the original error and leave a temp file | nit |
| clean-04 | 1 | sessions/store.py:42 | medium | Expired sessions no longer removed on get, so they accumulate until purge_expired is calle | nit |
| clean-04 | 2 | sessions/store.py:103 | medium | Bare except cleanup can mask the original error and leak the temp file | nit |
| clean-04 | 2 | sessions/store.py:42 | medium | Expired sessions are no longer removed on get, so they accumulate until purge_expired is c | nit |
| clean-04 | 2 | sessions/store.py:85 | low | A corrupt or partially written session file crashes startup | valid_issue |
| clean-10 | 2 | catalog/service.py:53 | medium | Missing/inactive product lookups are not negatively cached, and exceptions bypass cache; b | nit |
| clean-10 | 2 | catalog/service.py:75 | medium | Writes in the service can race with in-flight loads that were started before the write but | incorrect |
| clean-10 | 2 | catalog/service.py:94 | medium | remove() now has a check-then-delete race and ignores delete result | nit |
| real-01 | 1 | src/flask/testing.py:9 | low | urlsplit import still needed but removed usage in session_transaction | nit |
| real-08 | 0 | celery/worker/strategy.py:189 | medium | Task failure no longer recorded in result backend for invalid ETA | incorrect |
| real-08 | 1 | celery/worker/strategy.py:189 | medium | Failure no longer recorded in result backend for invalid ETA | nit |
| real-08 | 2 | celery/worker/strategy.py:189 | medium | Failure no longer recorded in result backend for invalid ETA | incorrect |
| seeded-api-02 | 0 | catalog/service.py:60 | low | Expired entry is popped, so cache may be evicted needlessly | incorrect |
| seeded-api-02 | 2 | catalog/service.py:60 | low | Expired entries are popped and refreshed handling is inconsistent with LRU eviction | nit |
| seeded-api-03 | 0 | notify/digest.py:46 | medium | Queue mutation during await can break iteration and drop entries | incorrect |
| seeded-api-03 | 1 | notify/digest.py:46 | medium | Mutating the dict during iteration once flush awaits | incorrect |
| seeded-api-03 | 2 | notify/digest.py:46 | medium | Queue mutation across await can drop or corrupt lines | nit |
| seeded-error-02 | 0 | pipeline/load.py:67 | low | Overly broad except Exception around parsing | nit |
| seeded-error-03 | 0 | billing/invoices.py:67 | low | Gateway is invoked with an idempotency_key keyword that RetryingGateway's positional signa | nit |
| seeded-error-04 | 0 | scheduler/runner.py:81 | low | Unbounded exponent in backoff computation can overflow | valid_issue |
| seeded-error-04 | 1 | scheduler/runner.py:81 | low | Unbounded exponent in backoff computation | nit |
| seeded-error-04 | 2 | scheduler/runner.py:82 | medium | Unbounded exponent in backoff can raise OverflowError | valid_issue |
| seeded-error-06 | 0 | auth/store.py:120 | medium | Unlocked reads race with the tmp-file write in FileSessionStore | nit |
| seeded-error-06 | 0 | auth/sessions.py:78 | medium | Refresh token is consumed before validation and the new session is issued separately | nit |
| seeded-error-06 | 1 | auth/sessions.py:104 | high | change_password swallows revocation failures, leaving old sessions alive | valid_issue |
| seeded-error-06 | 1 | auth/store.py:108 | medium | Unlocked reads race with writes and with the shared .tmp file | nit |
| seeded-error-06 | 1 | auth/sessions.py:78 | medium | Refresh token consumed before validation checks | nit |
| seeded-error-06 | 1 | auth/store.py:75 | low | MemorySessionStore.get reads without the lock | nit |
| seeded-error-06 | 2 | auth/sessions.py:104 | high | change_password silently leaves sessions alive when revocation fails | valid_issue |
| seeded-error-06 | 2 | auth/store.py:108 | medium | Unlocked reads race with non-atomic temp-file writes | incorrect |
| seeded-error-06 | 2 | auth/sessions.py:78 | medium | Refresh token consumed before validation; failed refresh destroys the session | nit |
| seeded-error-06 | 2 | auth/sessions.py:109 | medium | purge_expired aborts on the first store error and stays quadratic on the file store | valid_issue |
| seeded-logic-07 | 0 | metering/report.py:40 | medium | Zero previous total treated as missing | nit |
| seeded-logic-07 | 1 | metering/rollup.py:52 | medium | Sort key may break grouping by UTC day | nit |
| seeded-logic-07 | 2 | metering/report.py:40 | medium | Zero previous total treated the same as missing | nit |
| seeded-logic-08 | 0 | blobstore/store.py:80 | medium | Metadata written before blob leaves inconsistent state on failure | valid_issue |
| seeded-logic-08 | 0 | blobstore/store.py:103 | medium | head() can fail on a corrupt or partial metadata file | valid_issue |
| seeded-logic-08 | 1 | blobstore/store.py:81 | medium | Metadata written before blob; failed blob write leaves inconsistent state | valid_issue |
| seeded-logic-08 | 1 | blobstore/store.py:103 | medium | head() can crash on corrupt or non-dict metadata, and races with delete | valid_issue |
| seeded-logic-08 | 2 | blobstore/store.py:82 | medium | Metadata written before blob, leaving inconsistent state on failure | valid_issue |
| seeded-logic-08 | 2 | blobstore/store.py:103 | medium | Corrupt or unreadable metadata file crashes head | valid_issue |
| seeded-perf-03 | 0 | scheduling/sla.py:77 | medium | overdue_by_region returns every configured region, including those with no overdue tickets | incorrect |
| seeded-perf-03 | 1 | scheduling/sla.py:77 | medium | overdue_by_region silently drops overdue tickets for regions not in codes | incorrect |
| seeded-perf-03 | 2 | scheduling/sla.py:77 | medium | overdue_by_region drops tickets whose region is not configured | nit |
| seeded-perf-05 | 0 | newsletter/campaign.py:79 | medium | Render or other send errors abort the whole campaign with no report | valid_issue |
| seeded-perf-05 | 1 | newsletter/campaign.py:78 | medium | A non-RecipientRefused error aborts the whole send and discards the report | valid_issue |
| seeded-perf-05 | 1 | newsletter/campaign.py:49 | medium | Dedup marks address as seen only after eligibility checks, so later duplicate can slip thr | nit |
| seeded-perf-05 | 2 | newsletter/campaign.py:78 | medium | A single non-refusal send error aborts the whole campaign and the report is lost | valid_issue |

... 35 more (see scores.json / reviews.jsonl).

FP triage (advisory, never changes the headline): incorrect 13, nit 48, valid_issue 24
