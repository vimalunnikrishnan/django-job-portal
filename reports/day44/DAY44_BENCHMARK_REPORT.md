# Day 44 — Load Testing and Performance Benchmark

## Objective
Evaluate the response time and reliability of the Django job-list API using Locust.

**Endpoint:** `GET /api/jobs/list/`

## 1. Clean2 benchmark

| Metric | Result |
|---|---:|
| Total requests | 187 |
| Failed requests | 0 |
| Failure rate | 0% |
| Average response time | 6.08 ms |
| Median response time | 6 ms |
| 95th percentile response time | 8 ms |
| 99th percentile response time | 10 ms |
| Minimum response time | 2.97 ms |
| Maximum response time | 48.68 ms |
| Throughput | 3.21 requests/second |

**Result:** The clean2 run completed 187 requests with no recorded failures.

## 2. Smoke test

| Metric | Result |
|---|---:|
| Total requests | 8 |
| Failed requests | 0 |
| Average response time | 12.67 ms |
| Maximum response time | 66.93 ms |

**Result:** The smoke test completed without recorded failures. Its small request count makes it a basic validation, not a load-capacity benchmark.

## 3. Earlier test runs

The baseline run recorded 87 failures out of 187 requests. The clean run recorded 94 failures out of 194 requests. Their failure logs identify HTTP 429 Too Many Requests responses.

These runs were affected by rate limiting and are not used as successful reliability benchmarks. The clean2 run recorded zero failures.

## 4. Evidence files

- `day44_clean2_stats.csv` — clean2 request statistics
- `day44_clean2_stats_history.csv` — clean2 statistics history
- `day44_clean2_failures.csv` — clean2 failure report
- `day44_clean2_exceptions.csv` — clean2 exception report
- `day44_smoke_stats.csv` — smoke-test statistics
- `day44_smoke_stats_history.csv` — smoke-test statistics history
- `day44_smoke_failures.csv` — smoke-test failure report
- `day44_smoke_exceptions.csv` — smoke-test exception report

## 5. Limitations

- These are local development-environment results, not production benchmarks.
- The request rate and results depend on the local machine, test duration, user count, database, and configuration.
- The small smoke test does not establish maximum system capacity.
- The benchmark does not establish how the application behaves under sustained high concurrency.
- No performance improvement from the database index should be claimed without a suitable before-and-after comparison.

## Conclusion

The clean2 run provides a successful local API benchmark with zero recorded failures and a 6.08 ms average response time. Further controlled tests at increasing concurrency would be required to assess capacity and stability under heavier load.

