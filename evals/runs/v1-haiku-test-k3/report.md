# Eval run `v1-haiku-test-k3`

|  |  |
|---|---|
| Config | v1-haiku (backend anthropic, effort medium) |
| Model / prompt | claude-haiku-5-5 / v1 (hash 308e4c19584c) |
| Dataset | v1.0.0 (hash 8ad094c9ed2b) |
| Split / cases / k | test / 43 / 3 |
| Cases by kind | clean 8, real 6, seeded 29 |
| Must-find bugs (high+) | 42 (27) |
| Mode | record (batch) |
| Judge | claude-haiku-5-5 / same-defect-v2 |
| Location tolerance | ±3 lines |
| Created | 2026-10-26T18:39:46+00:00 (git dcf2686195 (dirty)) |
| CIs | 95% cluster bootstrap over cases, 10000 resamples |

## Headline

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| recall | 0.810 [0.689, 0.921] | 0.841 [0.740, 0.935] | 42 |
| recall_high | 0.840 [0.690, 0.971] | 0.852 [0.717, 0.971] | 27 |
| precision | 0.625 [0.509, 0.750] | 0.709 [0.580, 0.848] | 43 |
| precision_high | 0.967 [0.915, 1.000] | 0.967 [0.915, 1.000] | 43 |
| f1 | 0.704 [0.600, 0.802] | 0.768 [0.667, 0.862] | 42 |
| fp_per_case | 0.481 [0.287, 0.705] | 0.341 [0.155, 0.558] | 43 |

Strict = location candidate + judge `same`; location-only ignores the judge. Strict pairs with a judge error: 0, without a judgment: 0 (both count as not matched).

## Clean cases (false alarms)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| clean_false_alarm_rate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 8 |
| clean_fp_per_case | 0.583 [0.056, 1.333] | 0.583 [0.056, 1.333] | 8 |

`clean_false_alarm_rate` = share of clean cases with at least one finding of severity high or critical.

## Consistency over k samples

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| pass_all_k | 0.786 [0.649, 0.909] | 0.786 [0.649, 0.909] | 42 |
| pass_any_k | 0.857 [0.756, 0.951] | 0.929 [0.850, 1.000] | 42 |
| duplicate_rate | 0.000 [0.000, 0.000] | 0.084 [0.024, 0.155] | 43 |

pass^k = bug detected in every scorable sample; pass@k = in at least one.

## Severity / category agreement (on true-positive pairs)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| severity_exact | 0.570 [0.437, 0.696] | 0.576 [0.448, 0.700] | 102 |
| severity_within1 | 0.990 [0.968, 1.000] | 0.990 [0.969, 1.000] | 102 |
| category_accuracy | 0.725 [0.589, 0.853] | 0.717 [0.584, 0.843] | 102 |
| localization_mae | 0.05 [0.00, 0.13] | 0.06 [0.00, 0.13] | 102 |

## Slices

Slices with fewer than 6 units are marked INSUFFICIENT_DATA and cannot fail the gate.

| slice | value | cases | bugs | recall | precision | clean FA rate | recall (loc) | note |
|---|---|---|---|---|---|---|---|---|
| kind | clean | 8 | 0 | n/a | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | n/a |  |
| kind | real | 6 | 7 | 0.762 [0.389, 1.000] | 0.802 [0.565, 1.000] | n/a | 0.810 [0.556, 1.000] |  |
| kind | seeded | 29 | 35 | 0.819 [0.686, 0.939] | 0.668 [0.559, 0.795] | n/a | 0.848 [0.737, 0.949] |  |
| size_bucket | L | 9 | 11 | 0.758 [0.444, 1.000] | 0.526 [0.321, 0.770] | 0.000 [0.000, 0.000] | 0.788 [0.513, 1.000] |  |
| size_bucket | M | 20 | 19 | 0.860 [0.727, 1.000] | 0.608 [0.445, 0.791] | 0.000 [0.000, 0.000] | 0.860 [0.727, 1.000] |  |
| size_bucket | S | 14 | 12 | 0.778 [0.515, 1.000] | 0.801 [0.598, 0.970] | 0.000 [0.000, 0.000] | 0.861 [0.697, 1.000] |  |
| seeded_size_bucket | L | 8 | 11 | 0.758 [0.455, 1.000] | 0.579 [0.390, 0.833] | n/a | 0.788 [0.528, 1.000] |  |
| seeded_size_bucket | M | 16 | 19 | 0.860 [0.730, 1.000] | 0.686 [0.552, 0.846] | n/a | 0.860 [0.730, 1.000] |  |
| seeded_size_bucket | S | 5 | 5 | 0.800 [0.400, 1.000] | 0.867 [0.600, 1.000] | n/a | 0.933 [0.800, 1.000] | INSUFFICIENT_DATA |
| split | test | 43 | 42 | 0.810 [0.689, 0.921] | 0.625 [0.509, 0.750] | 0.000 [0.000, 0.000] | 0.841 [0.740, 0.935] |  |

| slice | value | bugs | recall | pass^k | recall (loc) | note |
|---|---|---|---|---|---|---|
| category_group | api_contract | 7 | 0.714 [0.429, 1.000] | 0.714 [0.429, 1.000] | 0.714 [0.429, 1.000] |  |
| category_group | error_handling | 7 | 0.857 [0.625, 1.000] | 0.857 [0.625, 1.000] | 0.857 [0.625, 1.000] |  |
| category_group | logic | 10 | 0.733 [0.444, 1.000] | 0.700 [0.364, 1.000] | 0.800 [0.576, 1.000] |  |
| category_group | performance | 6 | 0.722 [0.389, 1.000] | 0.667 [0.333, 1.000] | 0.833 [0.611, 1.000] |  |
| category_group | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| category_group | state | 6 | 0.889 [0.667, 1.000] | 0.833 [0.500, 1.000] | 0.889 [0.667, 1.000] |  |
| category | api_contract | 7 | 0.714 [0.429, 1.000] | 0.714 [0.429, 1.000] | 0.714 [0.429, 1.000] |  |
| category | concurrency | 3 | 0.778 [0.333, 1.000] | 0.667 [0.000, 1.000] | 0.778 [0.333, 1.000] | INSUFFICIENT_DATA |
| category | error_handling | 7 | 0.857 [0.625, 1.000] | 0.857 [0.625, 1.000] | 0.857 [0.625, 1.000] |  |
| category | logic | 10 | 0.733 [0.444, 1.000] | 0.700 [0.364, 1.000] | 0.800 [0.576, 1.000] |  |
| category | performance | 6 | 0.722 [0.389, 1.000] | 0.667 [0.333, 1.000] | 0.833 [0.611, 1.000] |  |
| category | resource | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | security | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | critical | 8 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| severity | high | 19 | 0.772 [0.588, 0.961] | 0.737 [0.524, 0.941] | 0.789 [0.630, 0.961] |  |
| severity | medium | 15 | 0.756 [0.524, 0.941] | 0.733 [0.500, 0.938] | 0.822 [0.643, 0.958] |  |
| tag | library_knowledge | 1 | 0.333 [0.333, 0.333] | 0.000 [0.000, 0.000] | 0.333 [0.333, 0.333] | INSUFFICIENT_DATA |
| tag | unshown_context | 4 | 0.333 [0.000, 0.750] | 0.250 [0.000, 0.750] | 0.333 [0.000, 0.750] | INSUFFICIENT_DATA |
| tag | untagged | 38 | 0.860 [0.739, 0.961] | 0.842 [0.703, 0.951] | 0.895 [0.800, 0.974] |  |

## Location tolerance sensitivity (point values)

| tol | recall | precision | f1 | recall (loc) | precision (loc) | judge err / missing |
|---|---|---|---|---|---|---|
| ±0 | 0.810 | 0.625 | 0.704 | 0.841 | 0.682 | 0 / 0 |
| ±3 (scored) | 0.810 | 0.625 | 0.704 | 0.841 | 0.709 | 0 / 0 |
| ±5 | 0.810 | 0.625 | 0.704 | 0.849 | 0.731 | 0 / 0 |
| ±10 | 0.810 | 0.625 | 0.704 | 0.857 | 0.757 | 0 / 0 |

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
| reviewer cost (USD) | 0.0725 |
| cost per review (USD) | 0.0006 |
| latency | not measured (batch, cached or synthetic) over 0 calls |
| tokens in / out | 583557 / 165844 |
| cache read / write | 332160 / 2595 |
| judge calls / errors | 138 / 0 |
| judge cost (USD) | 0.0232 |

## Missed bugs (strict detect rate < 1)

| case | bug | file:lines | severity | category | detect (strict) | detect (loc) |
|---|---|---|---|---|---|---|
| real-03 | b1 | pydantic/root_model.py:104-106 | medium | logic | 0.00 | 0.33 |
| seeded-api-06 | b2 | expenses/policy.py:22-22 | high | api_contract | 0.00 | 0.00 |
| seeded-api-08 | b1 | fleet/registry.py:33-35 | high | api_contract | 0.00 | 0.00 |
| seeded-error-03 | b1 | billing/retry.py:55-55 | medium | error_handling | 0.00 | 0.00 |
| seeded-logic-07 | b1 | metering/rollup.py:57-58 | high | logic | 0.00 | 0.33 |
| seeded-perf-05 | b1 | newsletter/campaign.py:78-81 | medium | performance | 0.00 | 0.67 |
| real-06 | b1 | scrapy/downloadermiddlewares/robotstxt.py:208-208 | high | concurrency | 0.33 | 0.33 |
| seeded-logic-07 | b2 | metering/report.py:69-69 | high | logic | 0.33 | 0.33 |
| seeded-perf-09 | b1 | i18n/bundles.py:43-44 | medium | performance | 0.33 | 0.33 |

## False positives (strict)

| case | sample | file:line | severity | title | triage |
|---|---|---|---|---|---|
| clean-02 | 1 | relnotes/git.py:37 | medium | Revision validation rejects valid git revisions containing spaces | valid_issue |
| clean-04 | 0 | sessions/store.py:42 | medium | Expired sessions are no longer evicted on access, so they accumulate until purge_expired r | valid_issue |
| clean-04 | 0 | sessions/store.py:37 | medium | Every create copies the whole session map, and FileSessionStore rewrites and fsyncs the fu | nit |
| clean-04 | 1 | sessions/store.py:43 | medium | get() no longer evicts expired sessions, so expired entries accumulate | nit |
| clean-04 | 1 | sessions/store.py:103 | low | Bare except and unguarded unlink can mask the original write error | nit |
| clean-04 | 1 | sessions/store.py:37 | medium | Every create() copies the whole session map and rewrites the entire file | nit |
| clean-04 | 2 | sessions/store.py:37 | medium | create() copies the whole session map on every login | nit |
| clean-04 | 2 | sessions/store.py:43 | medium | Expired sessions are no longer evicted on lookup | nit |
| clean-04 | 2 | sessions/store.py:98 | low | File descriptor leaks if os.fdopen fails | nit |
| clean-10 | 0 | catalog/service.py:92 | low | remove() no longer reports a failed delete | valid_issue |
| clean-10 | 1 | catalog/service.py:94 | low | remove() ignores the repository's delete result, so a concurrent delete now succeeds silen | nit |
| clean-10 | 1 | catalog/cache.py:67 | low | Any invalidation anywhere discards every in-flight load, so the cache stops storing under  | valid_issue |
| clean-10 | 2 | catalog/service.py:94 | medium | remove() ignores the repository's delete result, so a concurrent removal is reported as su | valid_issue |
| clean-12 | 2 | storage/blobs.py:37 | low | Rename is not made durable by fsyncing the parent directory | valid_issue |
| real-03 | 2 | pydantic/root_model.py:106 | medium | RootModel.__copy__ no longer carries over private attributes | incorrect |
| real-08 | 0 | celery/worker/strategy.py:189 | medium | Failure result is no longer recorded for the task | incorrect |
| real-08 | 1 | celery/worker/strategy.py:189 | medium | Failure is no longer recorded in the result backend | incorrect |
| real-08 | 2 | celery/worker/strategy.py:189 | medium | Failure is no longer recorded in the result backend | incorrect |
| seeded-api-02 | 0 | catalog/service.py:65 | medium | max_entries=0 makes find raise StopIteration | nit |
| seeded-api-02 | 2 | catalog/service.py:66 | medium | max_entries=0 makes find() raise StopIteration | valid_issue |
| seeded-api-02 | 2 | catalog/service.py:60 | low | find() now mutates shared cache state on reads | valid_issue |
| seeded-api-05 | 0 | tracking/reports.py:33 | medium | Public functions and store methods renamed without aliases | nit |
| seeded-api-05 | 2 | tracking/reports.py:33 | medium | Public report functions and store method renamed without compatibility aliases | nit |
| seeded-error-02 | 0 | pipeline/load.py:68 | medium | Malformed rows no longer abort the load; callers must check report.clean | nit |
| seeded-error-04 | 0 | scheduler/runner.py:81 | medium | Backoff exponent can overflow timedelta and raise out of tick() | valid_issue |
| seeded-error-04 | 1 | scheduler/runner.py:81 | medium | Backoff exponent can overflow timedelta and raise from inside the failure handler | valid_issue |
| seeded-error-04 | 2 | scheduler/runner.py:81 | medium | Backoff exponent can overflow timedelta and raise from inside the failure handler | valid_issue |
| seeded-error-06 | 0 | auth/sessions.py:85 | medium | Refresh consumes the old session before the new one is saved | valid_issue |
| seeded-error-06 | 0 | auth/store.py:109 | medium | Every authentication reads and parses the entire session file | nit |
| seeded-error-06 | 1 | auth/sessions.py:22 | medium | SessionManager constructor and login return type changed in a breaking way | nit |
| seeded-error-06 | 2 | auth/sessions.py:49 | medium | Constructor signature and session model changed for existing callers | nit |
| seeded-error-06 | 2 | auth/store.py:120 | medium | Whole-file rewrite on every change makes sign-out and purge quadratic | nit |
| seeded-logic-06 | 0 | ratelimit/limiter.py:71 | medium | Requests whose cost exceeds burst can never succeed | valid_issue |
| seeded-logic-06 | 1 | ratelimit/limiter.py:70 | medium | Cost above capacity can never be allowed, so the client is stuck with 429s | valid_issue |
| seeded-logic-07 | 0 | metering/cli.py:16 | low | MONTH_RE with $ accepts a trailing newline, which then matches no rows | nit |
| seeded-logic-07 | 1 | metering/rollup.py:56 | medium | Daily grouping can split one day into several totals when timestamps have mixed offsets | valid_issue |
| seeded-logic-07 | 1 | metering/cli.py:16 | low | MONTH_RE accepts a trailing newline in --month | nit |
| seeded-logic-07 | 2 | metering/cli.py:16 | low | Month regex accepts a trailing newline, producing a silent empty report | nit |
| seeded-logic-07 | 2 | metering/report.py:86 | low | CSV output does not neutralise spreadsheet formula prefixes in account IDs | nit |
| seeded-logic-08 | 0 | blobstore/store.py:81 | medium | Fixed temp file name for metadata races under concurrent puts to the same key | valid_issue |
| seeded-logic-08 | 0 | blobstore/store.py:82 | medium | Metadata is replaced before the blob, so a failed blob write leaves them mismatched | valid_issue |
| seeded-logic-08 | 0 | blobstore/store.py:97 | low | head() on a directory returns a BlobInfo instead of BlobNotFound | valid_issue |
| seeded-logic-08 | 1 | blobstore/store.py:83 | medium | Metadata is replaced before the blob, so a failed blob write leaves inconsistent state | valid_issue |
| seeded-logic-08 | 2 | blobstore/store.py:83 | medium | Metadata is replaced before the blob, so readers and failures see mismatched state | valid_issue |
| seeded-perf-03 | 0 | scheduling/sla.py:63 | high | overdue() return type changed from tuples to OverdueTicket objects | nit |
| seeded-perf-03 | 0 | scheduling/sla.py:57 | medium | One ticket with an unconfigured region aborts the whole overdue report | nit |
| seeded-perf-03 | 1 | scheduling/sla.py:48 | medium | start_day now takes a Ticket instead of a datetime, breaking existing callers | nit |
| seeded-perf-03 | 2 | scheduling/holidays.py:28 | high | Holiday file format changed, so existing data files are rejected | valid_issue |
| seeded-perf-03 | 2 | scheduling/sla.py:63 | medium | overdue() now returns OverdueTicket objects instead of (ticket, due) tuples | nit |
| seeded-perf-03 | 2 | scheduling/sla.py:34 | medium | Ticket gained a required region field, breaking existing constructors | nit |

... 12 more (see scores.json / reviews.jsonl).

FP triage (advisory, never changes the headline): incorrect 4, nit 33, valid_issue 25
