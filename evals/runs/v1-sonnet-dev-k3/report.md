# Eval run `v1-sonnet-dev-k3`

|  |  |
|---|---|
| Config | v1-sonnet (backend anthropic, effort medium) |
| Model / prompt | claude-sonnet-5-5 / v1 (hash 308e4c19584c) |
| Dataset | v1.0.0 (hash 8ad094c9ed2b) |
| Split / cases / k | dev / 29 / 3 |
| Cases by kind | clean 7, real 4, seeded 18 |
| Must-find bugs (high+) | 24 (17) |
| Mode | record (batch) |
| Judge | claude-haiku-5-5 / same-defect-v2 |
| Location tolerance | ±3 lines |
| Created | 2026-10-26T18:08:22+00:00 (git d884bc89c6 (dirty)) |
| CIs | 95% cluster bootstrap over cases, 10000 resamples |

## Headline

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| recall | 0.917 [0.800, 1.000] | 0.917 [0.800, 1.000] | 24 |
| recall_high | 0.882 [0.722, 1.000] | 0.882 [0.722, 1.000] | 17 |
| precision | 0.711 [0.559, 0.874] | 0.720 [0.571, 0.876] | 29 |
| precision_high | 0.961 [0.902, 1.000] | 0.961 [0.902, 1.000] | 29 |
| f1 | 0.801 [0.673, 0.915] | 0.806 [0.680, 0.917] | 24 |
| fp_per_case | 0.310 [0.115, 0.540] | 0.299 [0.115, 0.517] | 29 |

Strict = location candidate + judge `same`; location-only ignores the judge. Strict pairs with a judge error: 0, without a judgment: 0 (both count as not matched).

## Clean cases (false alarms)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| clean_false_alarm_rate | 0.048 [0.000, 0.167] | 0.048 [0.000, 0.167] | 7 |
| clean_fp_per_case | 0.333 [0.000, 0.833] | 0.333 [0.000, 0.833] | 7 |

`clean_false_alarm_rate` = share of clean cases with at least one finding of severity high or critical.

## Consistency over k samples

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| pass_all_k | 0.917 [0.800, 1.000] | 0.917 [0.800, 1.000] | 24 |
| pass_any_k | 0.917 [0.800, 1.000] | 0.917 [0.800, 1.000] | 24 |
| duplicate_rate | 0.022 [0.000, 0.067] | 0.032 [0.000, 0.078] | 29 |

pass^k = bug detected in every scorable sample; pass@k = in at least one.

## Severity / category agreement (on true-positive pairs)

| metric | strict (headline) | location-only | n |
|---|---|---|---|
| severity_exact | 0.561 [0.367, 0.754] | 0.561 [0.367, 0.754] | 66 |
| severity_within1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 66 |
| category_accuracy | 0.712 [0.536, 0.883] | 0.712 [0.536, 0.883] | 66 |
| localization_mae | 0.14 [0.00, 0.35] | 0.14 [0.00, 0.35] | 66 |

## Slices

Slices with fewer than 6 units are marked INSUFFICIENT_DATA and cannot fail the gate.

| slice | value | cases | bugs | recall | precision | clean FA rate | recall (loc) | note |
|---|---|---|---|---|---|---|---|---|
| kind | clean | 7 | 0 | n/a | 0.000 [0.000, 0.000] | 0.048 [0.000, 0.143] | n/a |  |
| kind | real | 4 | 4 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | n/a | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| kind | seeded | 18 | 20 | 0.900 [0.762, 1.000] | 0.733 [0.584, 0.906] | n/a | 0.900 [0.762, 1.000] |  |
| size_bucket | L | 4 | 4 | 0.750 [0.500, 1.000] | 0.510 [0.289, 0.889] | 0.333 [0.333, 0.333] | 0.750 [0.500, 1.000] | INSUFFICIENT_DATA |
| size_bucket | M | 11 | 8 | 0.875 [0.571, 1.000] | 0.633 [0.344, 1.000] | 0.000 [0.000, 0.000] | 0.875 [0.571, 1.000] |  |
| size_bucket | S | 14 | 12 | 1.000 [1.000, 1.000] | 0.879 [0.750, 1.000] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] |  |
| seeded_size_bucket | L | 3 | 4 | 0.750 [0.500, 1.000] | 0.567 [0.333, 1.000] | n/a | 0.750 [0.500, 1.000] | INSUFFICIENT_DATA |
| seeded_size_bucket | M | 7 | 8 | 0.875 [0.571, 1.000] | 0.737 [0.483, 1.000] | n/a | 0.875 [0.571, 1.000] |  |
| seeded_size_bucket | S | 8 | 8 | 1.000 [1.000, 1.000] | 0.830 [0.677, 1.000] | n/a | 1.000 [1.000, 1.000] |  |
| split | dev | 29 | 24 | 0.917 [0.800, 1.000] | 0.711 [0.559, 0.874] | 0.048 [0.000, 0.167] | 0.917 [0.800, 1.000] |  |

| slice | value | bugs | recall | pass^k | recall (loc) | note |
|---|---|---|---|---|---|---|
| category_group | api_contract | 4 | 0.750 [0.250, 1.000] | 0.750 [0.250, 1.000] | 0.750 [0.250, 1.000] | INSUFFICIENT_DATA |
| category_group | error_handling | 2 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category_group | logic | 9 | 0.889 [0.727, 1.000] | 0.889 [0.727, 1.000] | 0.889 [0.727, 1.000] |  |
| category_group | performance | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category_group | security | 4 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category_group | state | 2 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | api_contract | 4 | 0.750 [0.250, 1.000] | 0.750 [0.250, 1.000] | 0.750 [0.250, 1.000] | INSUFFICIENT_DATA |
| category | concurrency | 1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | error_handling | 2 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | logic | 9 | 0.889 [0.727, 1.000] | 0.889 [0.727, 1.000] | 0.889 [0.727, 1.000] |  |
| category | performance | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | resource | 1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| category | security | 4 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| severity | critical | 4 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| severity | high | 13 | 0.846 [0.647, 1.000] | 0.846 [0.647, 1.000] | 0.846 [0.647, 1.000] |  |
| severity | low | 1 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| severity | medium | 6 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |  |
| tag | library_knowledge | 3 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | INSUFFICIENT_DATA |
| tag | unshown_context | 6 | 0.833 [0.500, 1.000] | 0.833 [0.500, 1.000] | 0.833 [0.500, 1.000] |  |
| tag | untagged | 18 | 0.944 [0.842, 1.000] | 0.944 [0.842, 1.000] | 0.944 [0.842, 1.000] |  |

## Location tolerance sensitivity (point values)

| tol | recall | precision | f1 | recall (loc) | precision (loc) | judge err / missing |
|---|---|---|---|---|---|---|
| ±0 | 0.875 | 0.679 | 0.764 | 0.875 | 0.687 | 0 / 0 |
| ±3 (scored) | 0.917 | 0.711 | 0.801 | 0.917 | 0.720 | 0 / 0 |
| ±5 | 0.917 | 0.711 | 0.801 | 0.917 | 0.744 | 0 / 0 |
| ±10 | 0.917 | 0.711 | 0.801 | 0.917 | 0.744 | 0 / 0 |

## Serving outcomes

87 of 87 samples scorable (status `ok`). Other statuses are infra outcomes, excluded from quality metrics, never scored as 'no findings'.

| status | samples | share |
|---|---|---|
| ok | 87 | 1.000 |
| truncated | 0 | 0.000 |
| refused | 0 | 0.000 |
| schema_error | 0 | 0.000 |
| api_error | 0 | 0.000 |
| missing | 0 | 0.000 |

Findings on files outside the diff (dropped, counted): 0.

## Ops

|  |  |
|---|---|
| reviews | 87 |
| reviewer cost (USD) | 0.4853 |
| cost per review (USD) | 0.0056 |
| latency | not measured (batch, cached or synthetic) over 0 calls |
| tokens in / out | 300054 / 31942 |
| cache read / write | 223170 / 2595 |
| judge calls / errors | 72 / 0 |
| judge cost (USD) | 0.0125 |

## Missed bugs (strict detect rate < 1)

| case | bug | file:lines | severity | category | detect (strict) | detect (loc) |
|---|---|---|---|---|---|---|
| seeded-api-01 | b1 | scheduling/planner.py:53-53 | high | api_contract | 0.00 | 0.00 |
| seeded-logic-03 | b1 | billing/proration.py:39-39 | high | logic | 0.00 | 0.00 |

## False positives (strict)

| case | sample | file:line | severity | title | triage |
|---|---|---|---|---|---|
| clean-01 | 0 | reports/dashboard.py:64 | medium | Sort direction defaults to descending for every column when no prefix is given | nit |
| clean-01 | 0 | reports/dashboard.py:63 | medium | Blank status parameter is treated as no filter | nit |
| clean-01 | 1 | reports/dashboard.py:66 | low | Sort prefix handling accepts a bare "-" and silently changes the sort direction | nit |
| clean-01 | 2 | reports/dashboard.py:66 | medium | Sort prefix handling breaks the "-" direction and the "+" convention | nit |
| clean-01 | 2 | reports/orders_report.py:62 | medium | Empty status list is checked after unknown check but behaves differently from None | nit |
| clean-05 | 1 | flags/client.py:31 | high | DEFAULT_FLAGS silently merged in, changing is_enabled/require semantics | valid_issue |
| clean-05 | 1 | flags/cache.py:118 | medium | Stale serving extends checked_at but the max_stale bound is checked against a possibly shi | nit |
| seeded-api-01 | 0 | scheduling/planner.py:66 | medium | Rounded-up start can fall outside window or be pushed past the slot's free end, and tz-awa | nit |
| seeded-api-01 | 0 | scheduling/planner.py:85 | medium | Overlap check only against last pick; non-overlap contract and step spacing interplay | nit |
| seeded-api-01 | 2 | scheduling/planner.py:66 | medium | Rounding free-interval start can push slot start outside the window or free interval | incorrect |
| seeded-api-01 | 2 | scheduling/planner.py:85 | medium | Overlap check only compares to last pick, and with step < length makes suggestions dense | nit |
| seeded-api-01 | 2 | scheduling/planner.py:40 | medium | _round_up modulo uses hour-relative offset, wrong for steps not dividing an hour | incorrect |
| seeded-api-04 | 1 | contacts/parsing.py:38 | medium | Header validation error is now raised lazily | nit |
| seeded-api-04 | 2 | contacts/parsing.py:38 | medium | Missing-columns ValueError now raised lazily at first iteration | nit |
| seeded-logic-03 | 2 | billing/invoices.py:76 | medium | build_invoice drains pending lines as a side effect | valid_issue |
| seeded-logic-04 | 0 | salesreport/cli.py:30 | low | Empty export with both --since and --until falls through to the report | nit |
| seeded-logic-04 | 1 | salesreport/cli.py:30 | low | Empty export with both --since and --until falls through, and `or` is used for optional da | valid_issue |
| seeded-logic-04 | 2 | salesreport/cli.py:30 | low | Empty export with both --since and --until falls through, or the empty check is inconsiste | incorrect |
| seeded-perf-07 | 0 | podsync/client.py:64 | medium | Page past the end is returned as an empty page, indistinguishable from a real empty last p | valid_issue |
| seeded-perf-07 | 0 | podsync/store.py:87 | medium | mark_imported insert on a missing row leaves next_page at 0 and ignores checkpoint state | nit |
| seeded-perf-07 | 1 | podsync/store.py:87 | high | mark_imported inserts a row with next_page defaulting to 0 when none exists | nit |
| seeded-perf-07 | 1 | podsync/sync.py:86 | medium | Page upserts and checkpoint are not atomic; other ApiErrors leave progress inconsistent | nit |
| seeded-perf-07 | 2 | podsync/store.py:84 | medium | mark_imported on a fresh row leaves next_page at 0 and reset_import loses data | nit |
| seeded-perf-07 | 2 | podsync/sync.py:93 | medium | Checkpoint saved before completion is recorded; non-atomic with episode writes | nit |
| seeded-security-05 | 0 | mailer/dispatch.py:55 | medium | build_dispatcher's first parameter changed meaning and name | nit |
| seeded-security-05 | 1 | mailer/dispatch.py:55 | medium | build_dispatcher changes meaning of its first argument | nit |
| seeded-security-05 | 2 | mailer/dispatch.py:55 | medium | build_dispatcher signature change breaks existing callers | nit |

FP triage (advisory, never changes the headline): incorrect 3, nit 20, valid_issue 4
