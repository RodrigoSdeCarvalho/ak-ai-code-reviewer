# Eval run `v1-sonnet-test-k3-o3`

|  |  |
|---|---|
| Config | v1-sonnet (backend anthropic, effort medium) |
| Model / prompt | claude-sonnet-5-5 / v1 (hash 308e4c19584c) |
| Dataset | v1.0.0 (hash 8ad094c9ed2b) |
| Split / cases / k | test / 43 / 3 |
| Cases by kind | clean 8, real 6, seeded 29 |
| Must-find bugs (high+) | 42 (27) |
| Mode | record (batch) |
| Judge | claude-haiku-5-5 / same-defect-v2 |
| Location tolerance | ±3 lines |
| Created | 2026-10-26T18:47:41+00:00 (git 11029931b4 (dirty)) |
| CIs | 95% cluster bootstrap over cases, 10000 resamples |

## Headline

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| recall | 0.841 [0.735, 0.932] | 0.889 [0.803, 0.963] | 42 |
| recall_high | 0.864 [0.741, 0.970] | 0.901 [0.795, 0.987] | 27 |
| precision | 0.568 [0.463, 0.687] | 0.679 [0.564, 0.805] | 43 |
| precision_high | 0.974 [0.937, 1.000] | 0.987 [0.960, 1.000] | 43 |
| f1 | 0.677 [0.580, 0.771] | 0.770 [0.681, 0.854] | 42 |
| fp_per_case | 0.628 [0.380, 0.907] | 0.411 [0.209, 0.651] | 43 |

Strict = location candidate + judge `same`; location-only ignores the judge. Strict pairs with a judge error: 0, without a judgment: 0 (both count as not matched).

## Clean cases (false alarms)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 8 |
| clean_fp_per_case | 0.292 [0.000, 0.867] | 0.292 [0.000, 0.867] | 8 |

`clean_false_alarm_rate` = share of clean cases with at least one finding of severity high or critical.

## Consistency over k samples

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| pass_all_k | 0.786 [0.659, 0.897] | 0.833 [0.721, 0.932] | 42 |
| pass_any_k | 0.881 [0.773, 0.974] | 0.929 [0.844, 1.000] | 42 |
| duplicate_rate | 0.000 [0.000, 0.000] | 0.117 [0.053, 0.183] | 43 |

pass^k = bug detected in every scorable sample; pass@k = in at least one.

## Severity / category agreement (on true-positive pairs)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| severity_exact | 0.555 [0.410, 0.694] | 0.561 [0.420, 0.696] | 106 |
| severity_within1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 106 |
| category_accuracy | 0.784 [0.654, 0.904] | 0.751 [0.617, 0.874] | 106 |
| localization_mae | 0.14 [0.00, 0.39] | 0.16 [0.00, 0.40] | 106 |

## Slices

Slices with fewer than 6 units are marked INSUFFICIENT_DATA and cannot fail the gate.

| slice | value | cases | bugs | recall | precision | clean FA rate | recall (loc) | note |
|---|---|---|---|---|---|---|---|---|
| kind | clean | 8 | 0 | n/a | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | n/a |  |
| kind | real | 6 | 7 | 0.810 [0.444, 1.000] | 0.849 [0.625, 1.000] | n/a | 0.810 [0.444, 1.000] |  |
| kind | seeded | 29 | 35 | 0.848 [0.737, 0.944] | 0.558 [0.453, 0.685] | n/a | 0.905 [0.820, 0.980] |  |
| size_bucket | L | 9 | 11 | 0.788 [0.500, 1.000] | 0.467 [0.280, 0.737] | 0.000 [0.000, 0.000] | 0.848 [0.625, 1.000] |  |
| size_bucket | M | 20 | 19 | 0.895 [0.789, 1.000] | 0.532 [0.406, 0.673] | 0.000 [0.000, 0.000] | 0.912 [0.807, 1.000] |  |
| size_bucket | S | 14 | 12 | 0.806 [0.556, 1.000] | 0.828 [0.607, 1.000] | 0.000 [0.000, 0.000] | 0.889 [0.694, 1.000] |  |
| seeded_size_bucket | L | 8 | 11 | 0.788 [0.500, 0.976] | 0.467 [0.282, 0.734] | n/a | 0.848 [0.630, 0.976] |  |
| seeded_size_bucket | M | 16 | 19 | 0.895 [0.794, 1.000] | 0.575 [0.455, 0.715] | n/a | 0.912 [0.810, 1.000] |  |
| seeded_size_bucket | S | 5 | 5 | 0.800 [0.400, 1.000] | 0.800 [0.400, 1.000] | n/a | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| split | test | 43 | 42 | 0.841 [0.735, 0.932] | 0.568 [0.463, 0.687] | 0.000 [0.000, 0.000] | 0.889 [0.803, 0.963] |  |

| slice | value | bugs | recall | pass^k | recall (loc) | note |
|---|---|---|---|---|---|---|
| category_group | api_contract | 7 | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] |  |
| category_group | error_handling | 7 | 0.857 [0.741, 1.000] | 0.714 [0.556, 1.000] | 0.857 [0.741, 1.000] |  |
| category_group | logic | 10 | 0.933 [0.833, 1.000] | 0.800 [0.500, 1.000] | 0.967 [0.889, 1.000] |  |
| category_group | performance | 6 | 0.667 [0.333, 1.000] | 0.667 [0.333, 1.000] | 0.944 [0.833, 1.000] |  |
| category_group | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| category_group | state | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| category | api_contract | 7 | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] | 0.571 [0.286, 0.857] |  |
| category | concurrency | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | error_handling | 7 | 0.857 [0.741, 1.000] | 0.714 [0.556, 1.000] | 0.857 [0.741, 1.000] |  |
| category | logic | 10 | 0.933 [0.833, 1.000] | 0.800 [0.500, 1.000] | 0.967 [0.889, 1.000] |  |
| category | performance | 6 | 0.667 [0.333, 1.000] | 0.667 [0.333, 1.000] | 0.944 [0.833, 1.000] |  |
| category | resource | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | critical | 8 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | high | 19 | 0.807 [0.648, 0.947] | 0.737 [0.529, 0.905] | 0.860 [0.719, 0.981] |  |
| severity | medium | 15 | 0.800 [0.595, 0.961] | 0.733 [0.500, 0.938] | 0.867 [0.690, 1.000] |  |
| tag | library_knowledge | 1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| tag | unshown_context | 4 | 0.583 [0.167, 1.000] | 0.500 [0.000, 1.000] | 0.583 [0.167, 1.000] | INSUFFICIENT_DATA |
| tag | untagged | 38 | 0.868 [0.765, 0.956] | 0.816 [0.692, 0.923] | 0.921 [0.842, 0.983] |  |

## Location tolerance sensitivity (point values)

| tol | recall | precision | f1 | recall (loc) | precision (loc) | judge err / missing |
|---|---|---|---|---|---|---|
| ±0 | 0.841 | 0.568 | 0.677 | 0.873 | 0.609 | 0 / 0 |
| ±3 (scored) | 0.841 | 0.568 | 0.677 | 0.889 | 0.679 | 0 / 0 |
| ±5 | 0.841 | 0.568 | 0.677 | 0.897 | 0.698 | 0 / 0 |
| ±10 | 0.841 | 0.568 | 0.677 | 0.897 | 0.756 | 0 / 0 |

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
| reviewer cost (USD) | 0.8989 |
| cost per review (USD) | 0.0070 |
| latency | not measured (batch, cached or synthetic) over 0 calls |
| tokens in / out | 583557 / 55784 |
| cache read / write | 332160 / 2595 |
| judge calls / errors | 160 / 0 |
| judge cost (USD) | 0.0128 |

## Missed bugs (strict detect rate < 1)

| case | bug | file:lines | severity | category | detect (strict) | detect (loc) |
|---|---|---|---|---|---|---|
| real-05 | b1 | src/click/_utils.py:15-21 | medium | api_contract | 0.00 | 0.00 |
| seeded-api-06 | b2 | expenses/policy.py:22-22 | high | api_contract | 0.00 | 0.00 |
| seeded-api-08 | b1 | fleet/registry.py:33-35 | high | api_contract | 0.00 | 0.00 |
| seeded-perf-05 | b1 | newsletter/campaign.py:78-81 | medium | performance | 0.00 | 1.00 |
| seeded-perf-08 | b1 | adserve/pacing.py:72-72 | high | performance | 0.00 | 0.67 |
| seeded-error-03 | b1 | billing/retry.py:55-55 | medium | error_handling | 0.33 | 0.33 |
| real-03 | b1 | pydantic/root_model.py:104-106 | medium | logic | 0.67 | 0.67 |
| seeded-error-06 | b2 | auth/sessions.py:98-100 | high | error_handling | 0.67 | 0.67 |
| seeded-logic-08 | b1 | blobstore/store.py:73-80 | high | logic | 0.67 | 1.00 |

## False positives (strict)

| case | sample | file:line | severity | title | triage |
|---|---|---|---|---|---|
| clean-04 | 0 | sessions/store.py:103 | medium | Bare except with unguarded os.unlink can mask the original error | - |
| clean-04 | 0 | sessions/store.py:42 | low | Expired sessions no longer removed on get | - |
| clean-04 | 1 | sessions/store.py:103 | medium | Bare except with unguarded os.unlink can mask the original error | - |
| clean-04 | 1 | sessions/store.py:42 | low | get() no longer evicts expired sessions | - |
| clean-04 | 2 | sessions/store.py:103 | medium | Bare except with unguarded unlink can mask the original error | - |
| clean-04 | 2 | sessions/store.py:106 | low | Memory update after replace can diverge from disk | - |
| clean-14 | 2 | audit/handlers.py:50 | low | Oversized cursor digits raise an uncaught ValueError (500 instead of 400) | - |
| real-08 | 0 | celery/worker/strategy.py:189 | medium | Task failure no longer recorded in result backend | - |
| real-08 | 1 | celery/worker/strategy.py:189 | medium | Failure no longer recorded in result backend | - |
| real-08 | 2 | celery/worker/strategy.py:189 | medium | Failure no longer recorded in result backend for invalid ETA | - |
| seeded-api-02 | 1 | catalog/service.py:60 | low | Cache hit refreshes LRU order but not the timestamp, and expired entries are handled incon | - |
| seeded-api-03 | 0 | notify/digest.py:46 | medium | Queue mutation across await can drop or corrupt lines | - |
| seeded-api-03 | 1 | notify/digest.py:41 | medium | Iterating the pending dict across awaits while add() can mutate it | - |
| seeded-api-03 | 2 | notify/digest.py:46 | medium | Mutating the list and deleting the dict key across an await can lose lines or raise | - |
| seeded-error-02 | 0 | pipeline/load.py:67 | low | Over-broad except Exception hides non-parse bugs | - |
| seeded-error-02 | 2 | pipeline/load.py:67 | medium | Over-broad `except Exception` hides programming errors as row rejections | - |
| seeded-error-04 | 2 | scheduler/runner.py:81 | medium | Unbounded exponent in backoff computation can overflow | - |
| seeded-error-06 | 0 | auth/sessions.py:83 | medium | Refresh token is consumed before validation and the user lookup is not guarded | - |
| seeded-error-06 | 0 | auth/sessions.py:113 | medium | purge_expired does not tolerate StoreError, unlike sign_out_everywhere | - |
| seeded-error-06 | 0 | auth/store.py:109 | medium | Unlocked reads race with the writer | - |
| seeded-error-06 | 1 | auth/store.py:121 | medium | File store get/all read without the lock | - |
| seeded-error-06 | 1 | auth/sessions.py:85 | medium | Refresh token consumed before validity checks, and new session issue can fail after consum | - |
| seeded-error-06 | 1 | auth/sessions.py:113 | medium | purge_expired aborts on the first store error | - |
| seeded-error-06 | 1 | auth/sessions.py:93 | high | sign_out_everywhere can miss concurrently created sessions and leaves refresh race | - |
| seeded-error-06 | 2 | auth/store.py:108 | medium | Unlocked reads race with writes, and readers share the temp file | - |
| seeded-error-06 | 2 | auth/sessions.py:109 | medium | purge_expired aborts midway on a StoreError and its count is unreliable | - |
| seeded-error-06 | 2 | auth/sessions.py:78 | medium | Refresh consumes the old session before validation and issuing, so a failure loses the ses | - |
| seeded-logic-06 | 0 | ratelimit/middleware.py:54 | low | Burst smaller than request cost makes expensive requests permanently denied | - |
| seeded-logic-07 | 0 | metering/report.py:40 | low | Zero previous total conflated with missing | - |
| seeded-logic-07 | 2 | metering/report.py:40 | low | Zero previous total hidden while previous_total is shown | - |
| seeded-logic-08 | 0 | blobstore/store.py:81 | medium | Metadata written before blob, leaving inconsistent state on failure | - |
| seeded-logic-08 | 0 | blobstore/store.py:103 | medium | head can raise on corrupt metadata or when the file is deleted concurrently | - |
| seeded-logic-08 | 0 | blobstore/store.py:120 | medium | Key-validation gap: user key can collide with metadata files | - |
| seeded-logic-08 | 1 | blobstore/store.py:73 | high | Mutable default argument is mutated by setdefault | - |
| seeded-logic-08 | 1 | blobstore/store.py:81 | medium | Metadata written before blob; failure or key collision leaves inconsistent state | - |
| seeded-logic-08 | 1 | blobstore/store.py:103 | medium | Corrupt or non-dict metadata file crashes head() | - |
| seeded-logic-08 | 2 | blobstore/store.py:81 | medium | Metadata written before blob; failed blob write leaves inconsistent state | - |
| seeded-logic-08 | 2 | blobstore/store.py:103 | medium | head can fail on a missing or corrupt metadata file | - |
| seeded-perf-05 | 0 | newsletter/campaign.py:79 | medium | Render failure aborts the whole campaign mid-send | - |
| seeded-perf-05 | 1 | newsletter/campaign.py:79 | medium | Render failure aborts the whole campaign mid-send | - |
| seeded-perf-05 | 2 | newsletter/campaign.py:79 | medium | Render failure aborts the whole campaign mid-send | - |
| seeded-perf-06 | 0 | greenhouse/irrigation.py:35 | low | Misleading reason when a zone is inspected because of a low rejected share check | - |
| seeded-perf-06 | 2 | greenhouse/irrigation.py:35 | low | Inspect reason is misleading when there are no rejected readings | - |
| seeded-perf-08 | 0 | adserve/ledger.py:58 | medium | Invalid marker keyed only by impression id, not campaign | - |
| seeded-perf-08 | 0 | adserve/ledger.py:65 | medium | Whole day file re-read and parsed on every bid check | - |
| seeded-perf-08 | 0 | adserve/pacing.py:61 | medium | Hourly bucketing ignores timezone consistency with request time | - |
| seeded-perf-08 | 1 | adserve/ledger.py:58 | medium | Invalid marker is keyed only by impression id and lacks campaign | - |
| seeded-perf-08 | 1 | adserve/ledger.py:65 | medium | Whole day file re-read and parsed for every campaign on every bid | - |
| seeded-perf-08 | 1 | adserve/pacing.py:61 | medium | Hourly bucket uses impression's own timezone hour, not the request's | - |
| seeded-perf-08 | 2 | adserve/ledger.py:58 | medium | Invalid marker keyed only by impression id is dropped if the impression's day differs | - |

... 31 more (see scores.json / reviews.jsonl).
