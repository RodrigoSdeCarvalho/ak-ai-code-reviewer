# Eval run `static-test-k1`

|  |  |
|---|---|
| Config | static (backend static, effort -) |
| Model / prompt | - / - (hash n/a) |
| Dataset | v1.0.0 (hash 8ad094c9ed2b) |
| Split / cases / k | test / 43 / 1 |
| Cases by kind | clean 8, real 6, seeded 29 |
| Must-find bugs (high+) | 42 (27) |
| Mode | record |
| Judge | claude-haiku-5-5 / same-defect-v2 |
| Location tolerance | ±3 lines |
| Created | 2026-10-26T18:45:47+00:00 (git 11029931b4 (dirty)) |
| CIs | 95% cluster bootstrap over cases, 10000 resamples |

## Headline

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| recall | 0.024 [0.000, 0.077] | 0.071 [0.000, 0.158] | 42 |
| recall_high | 0.037 [0.000, 0.129] | 0.074 [0.000, 0.192] | 27 |
| precision | 0.071 [0.000, 0.188] | 0.214 [0.000, 0.444] | 43 |
| precision_high | n/a | n/a | 43 |
| f1 | 0.036 [0.000, 0.105] | 0.107 [0.000, 0.218] | 42 |
| fp_per_case | 0.302 [0.140, 0.488] | 0.256 [0.093, 0.442] | 43 |

Strict = location candidate + judge `same`; location-only ignores the judge. Strict pairs with a judge error: 0, without a judgment: 0 (both count as not matched).

## Clean cases (false alarms)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 8 |
| clean_fp_per_case | 0.125 [0.000, 0.400] | 0.125 [0.000, 0.400] | 8 |

`clean_false_alarm_rate` = share of clean cases with at least one finding of severity high or critical.

## Consistency over k samples

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| pass_all_k | 0.024 [0.000, 0.077] | 0.071 [0.000, 0.158] | 42 |
| pass_any_k | 0.024 [0.000, 0.077] | 0.071 [0.000, 0.158] | 42 |
| duplicate_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 43 |

pass^k = bug detected in every scorable sample; pass@k = in at least one.

## Severity / category agreement (on true-positive pairs)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| severity_exact | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1 |
| severity_within1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1 |
| category_accuracy | 1.000 [1.000, 1.000] | 0.667 [0.000, 1.000] | 1 |
| localization_mae | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 1 |

## Slices

Slices with fewer than 6 units are marked INSUFFICIENT_DATA and cannot fail the gate.

| slice | value | cases | bugs | recall | precision | clean FA rate | recall (loc) | note |
|---|---|---|---|---|---|---|---|---|
| kind | clean | 8 | 0 | n/a | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | n/a |  |
| kind | real | 6 | 7 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | n/a | 0.143 [0.000, 0.500] |  |
| kind | seeded | 29 | 35 | 0.029 [0.000, 0.088] | 0.083 [0.000, 0.207] | n/a | 0.057 [0.000, 0.143] |  |
| size_bucket | L | 9 | 11 | 0.091 [0.000, 0.250] | 0.167 [0.000, 0.333] | 0.000 [0.000, 0.000] | 0.091 [0.000, 0.250] |  |
| size_bucket | M | 20 | 19 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.053 [0.000, 0.182] |  |
| size_bucket | S | 14 | 12 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.083 [0.000, 0.273] |  |
| seeded_size_bucket | L | 8 | 11 | 0.091 [0.000, 0.250] | 0.167 [0.000, 0.333] | n/a | 0.091 [0.000, 0.250] |  |
| seeded_size_bucket | M | 16 | 19 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | n/a | 0.053 [0.000, 0.176] |  |
| seeded_size_bucket | S | 5 | 5 | 0.000 [0.000, 0.000] | n/a | n/a | 0.000 [0.000, 0.000] | INSUFFICIENT_DATA |
| split | test | 43 | 42 | 0.024 [0.000, 0.077] | 0.071 [0.000, 0.188] | 0.000 [0.000, 0.000] | 0.071 [0.000, 0.158] |  |

| slice | value | bugs | recall | pass^k | recall (loc) | note |
|---|---|---|---|---|---|---|
| category_group | api_contract | 7 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| category_group | error_handling | 7 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| category_group | logic | 10 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.200 [0.000, 0.500] |  |
| category_group | performance | 6 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| category_group | security | 6 | 0.167 [0.000, 0.375] | 0.167 [0.000, 0.375] | 0.167 [0.000, 0.375] |  |
| category_group | state | 6 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| category | api_contract | 7 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| category | concurrency | 3 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | INSUFFICIENT_DATA |
| category | error_handling | 7 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| category | logic | 10 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.200 [0.000, 0.500] |  |
| category | performance | 6 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| category | resource | 3 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | INSUFFICIENT_DATA |
| category | security | 6 | 0.167 [0.000, 0.375] | 0.167 [0.000, 0.375] | 0.167 [0.000, 0.375] |  |
| severity | critical | 8 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |  |
| severity | high | 19 | 0.053 [0.000, 0.167] | 0.053 [0.000, 0.167] | 0.105 [0.000, 0.278] |  |
| severity | medium | 15 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.067 [0.000, 0.214] |  |
| tag | library_knowledge | 1 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | INSUFFICIENT_DATA |
| tag | unshown_context | 4 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | INSUFFICIENT_DATA |
| tag | untagged | 38 | 0.026 [0.000, 0.081] | 0.026 [0.000, 0.081] | 0.079 [0.000, 0.171] |  |

## Location tolerance sensitivity (point values)

| tol | recall | precision | f1 | recall (loc) | precision (loc) | judge err / missing |
|---|---|---|---|---|---|---|
| ±0 | 0.024 | 0.071 | 0.036 | 0.071 | 0.214 | 0 / 0 |
| ±3 (scored) | 0.024 | 0.071 | 0.036 | 0.071 | 0.214 | 0 / 0 |
| ±5 | 0.024 | 0.071 | 0.036 | 0.071 | 0.214 | 0 / 0 |
| ±10 | 0.024 | 0.071 | 0.036 | 0.071 | 0.231 | 0 / 0 |

## Serving outcomes

43 of 43 samples scorable (status `ok`). Other statuses are infra outcomes, excluded from quality metrics, never scored as 'no findings'.

| status | samples | share |
|---|---|---|
| ok | 43 | 1.000 |
| truncated | 0 | 0.000 |
| refused | 0 | 0.000 |
| schema_error | 0 | 0.000 |
| api_error | 0 | 0.000 |
| missing | 0 | 0.000 |

Findings on files outside the diff (dropped, counted): 0.

## Ops

|  |  |
|---|---|
| reviews | 43 |
| reviewer cost (USD) | 0.0000 |
| cost per review (USD) | 0.0000 |
| latency | p50 436 ms, p95 500 ms over 43 calls |
| tokens in / out | 0 / 0 |
| cache read / write | 0 / 0 |
| judge calls / errors | 4 / 0 |
| judge cost (USD) | 0.0006 |

## Missed bugs (strict detect rate < 1)

| case | bug | file:lines | severity | category | detect (strict) | detect (loc) |
|---|---|---|---|---|---|---|
| real-01 | b1 | src/flask/app.py:724-735 | medium | logic | 0.00 | 0.00 |
| real-01 | b2 | src/flask/testing.py:180-180 | medium | logic | 0.00 | 0.00 |
| real-03 | b1 | pydantic/root_model.py:104-106 | medium | logic | 0.00 | 0.00 |
| real-04 | b1 | fastapi/dependencies/utils.py:1070-1078 | medium | logic | 0.00 | 1.00 |
| real-05 | b1 | src/click/_utils.py:15-21 | medium | api_contract | 0.00 | 0.00 |
| real-06 | b1 | scrapy/downloadermiddlewares/robotstxt.py:208-208 | high | concurrency | 0.00 | 0.00 |
| real-08 | b1 | celery/worker/strategy.py:187-189 | medium | error_handling | 0.00 | 0.00 |
| seeded-api-02 | b1 | catalog/service.py:63-68 | high | api_contract | 0.00 | 0.00 |
| seeded-api-03 | b1 | notify/digest.py:45-45 | critical | concurrency | 0.00 | 0.00 |
| seeded-api-05 | b1 | tracking/store.py:48-48 | high | api_contract | 0.00 | 0.00 |
| seeded-api-06 | b1 | expenses/approval.py:26-26 | high | api_contract | 0.00 | 0.00 |
| seeded-api-06 | b2 | expenses/policy.py:22-22 | high | api_contract | 0.00 | 0.00 |
| seeded-api-08 | b1 | fleet/registry.py:33-35 | high | api_contract | 0.00 | 0.00 |
| seeded-api-09 | b1 | helpdesk/tickets.py:39-40 | high | api_contract | 0.00 | 0.00 |
| seeded-error-02 | b1 | pipeline/load.py:64-67 | critical | error_handling | 0.00 | 0.00 |
| seeded-error-03 | b1 | billing/retry.py:55-55 | medium | error_handling | 0.00 | 0.00 |
| seeded-error-03 | b2 | billing/retry.py:61-61 | high | error_handling | 0.00 | 0.00 |
| seeded-error-04 | b1 | scheduler/runner.py:75-76 | medium | error_handling | 0.00 | 0.00 |
| seeded-error-06 | b1 | auth/store.py:139-140 | critical | error_handling | 0.00 | 0.00 |
| seeded-error-06 | b2 | auth/sessions.py:98-100 | high | error_handling | 0.00 | 0.00 |
| seeded-logic-05 | b1 | textkit/keywords.py:61-61 | high | logic | 0.00 | 0.00 |
| seeded-logic-06 | b1 | ratelimit/limiter.py:69-73 | high | logic | 0.00 | 0.00 |
| seeded-logic-07 | b1 | metering/rollup.py:57-58 | high | logic | 0.00 | 0.00 |
| seeded-logic-07 | b2 | metering/report.py:69-69 | high | logic | 0.00 | 0.00 |
| seeded-logic-08 | b1 | blobstore/store.py:73-80 | high | logic | 0.00 | 1.00 |
| seeded-perf-02 | b1 | inventory/stocktake.py:51-54 | medium | performance | 0.00 | 0.00 |
| seeded-perf-03 | b1 | scheduling/calendar.py:37-38 | medium | performance | 0.00 | 0.00 |
| seeded-perf-05 | b1 | newsletter/campaign.py:78-81 | medium | performance | 0.00 | 0.00 |
| seeded-perf-06 | b1 | greenhouse/readings.py:49-49 | medium | performance | 0.00 | 0.00 |
| seeded-perf-08 | b1 | adserve/pacing.py:72-72 | high | performance | 0.00 | 0.00 |
| seeded-perf-09 | b1 | i18n/bundles.py:43-44 | medium | performance | 0.00 | 0.00 |
| seeded-security-01 | b1 | bookclub/handlers.py:76-76 | critical | security | 0.00 | 0.00 |
| seeded-security-04 | b2 | workspace/invites.py:98-98 | medium | security | 0.00 | 0.00 |
| seeded-security-06 | b1 | boxoffice/handlers.py:96-96 | critical | security | 0.00 | 0.00 |
| seeded-security-07 | b1 | kanban/service.py:103-103 | critical | security | 0.00 | 0.00 |
| seeded-security-08 | b1 | loyalty/cors.py:42-42 | high | security | 0.00 | 0.00 |
| seeded-state-01 | b1 | inventory/service.py:93-96 | critical | resource | 0.00 | 0.00 |
| seeded-state-02 | b1 | storage/blobs.py:65-66 | high | resource | 0.00 | 0.00 |
| seeded-state-03 | b1 | billing/ratecache.py:107-107 | medium | resource | 0.00 | 0.00 |
| seeded-state-06 | b1 | pipeline/runner.py:51-51 | high | concurrency | 0.00 | 0.00 |
| seeded-state-06 | b2 | pipeline/runner.py:42-42 | critical | logic | 0.00 | 0.00 |

## False positives (strict)

| case | sample | file:line | severity | title | triage |
|---|---|---|---|---|---|
| clean-06 | 0 | readability/metrics.py:41 | medium | B006: Do not use mutable data structures for argument defaults | - |
| real-04 | 0 | fastapi/dependencies/utils.py:1070 | low | PLW2901: `for` loop variable `value` overwritten by assignment target | - |
| seeded-logic-07 | 0 | metering/report.py:98 | medium | B905: `zip()` without an explicit `strict=` parameter | - |
| seeded-logic-08 | 0 | blobstore/store.py:73 | medium | B006: Do not use mutable data structures for argument defaults | - |
| seeded-perf-03 | 0 | scheduling/calendar.py:22 | low | PLR2004: Magic value used in comparison, consider replacing `7` with a constant variable | - |
| seeded-perf-03 | 0 | scheduling/calendar.py:24 | low | PLR2004: Magic value used in comparison, consider replacing `24` with a constant variable | - |
| seeded-perf-09 | 0 | i18n/locales.py:14 | low | PLR2004: Magic value used in comparison, consider replacing `2` with a constant variable | - |
| seeded-perf-09 | 0 | i18n/locales.py:16 | low | PLR2004: Magic value used in comparison, consider replacing `4` with a constant variable | - |
| seeded-security-04 | 0 | workspace/invites.py:57 | low | PLR0913: Too many arguments in function definition (6 > 5) | - |
| seeded-security-04 | 0 | workspace/members.py:44 | low | PLR0913: Too many arguments in function definition (6 > 5) | - |
| seeded-security-06 | 0 | boxoffice/store.py:63 | low | PLR0913: Too many arguments in function definition (6 > 5) | - |
| seeded-security-07 | 0 | kanban/service.py:92 | low | PLR0913: Too many arguments in function definition (6 > 5) | - |
| seeded-state-06 | 0 | pipeline/runner.py:24 | low | PLR0913: Too many arguments in function definition (6 > 5) | - |
