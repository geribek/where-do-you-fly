# GET /api/v1/display
Local POC, no query parameters or credentials. HTTP 200 for handled operational states; framework/server errors may return 5xx. Firmware must retain its last screen and retry after 60 seconds on non-200, malformed JSON, oversized response or unsupported version. Interactive schema: `/docs`; machine schema: `/openapi.json`.

```json
{"version":1,"status":"ok","generated_at":"2026-09-25T05:00:00+00:00","observed_at":"2026-09-25T05:00:00+00:00","next_poll_at":"2026-09-25T05:05:00+00:00","retry_after_s":300,"stale":false,"flight":{"id":"mock-001","callsign":"DEMO001","origin":"AAA","destination":"XXX","aircraft":"A321"},"category":"inbound"}
```

| Field | Meaning |
|---|---|
| version | Integer 1; incompatible versions must be rejected |
| status | ok, empty, sleep, budget, error |
| generated_at | Aware ISO 8601 response time |
| observed_at | Successful mock observation time, including empty results; null if none |
| next_poll_at | Next five-minute active slot, aware ISO 8601 |
| retry_after_s | Positive integer seconds until next active slot; devices need no reliable RTC for POC |
| stale | false in Phase 1; reserved for future stale data policy |
| flight | One object for ok; otherwise null |
| category | inbound/outbound/nearby for ok, otherwise null |

Flight id is a bounded opaque string. Nullable callsign/route/type fields render as Unknown/???. Device payloads omit position coordinates. The backend retains them privately for filtering and ranking. There are no altitude/speed unit ambiguities because these fields are deferred. Additive fields may be ignored. Successful payloads are expected below 1 KiB; firmware allows up to 4 KiB. Responses include no provider key, raw provider record or spending details.

`empty` means no valid in-radius candidates. `sleep` overrides cached flight outside the schedule. `budget` means insufficient reserved budget for another poll. `error` means failed fixture validation/read or a concurrent in-progress reservation. These states never trigger immediate provider retries. Missing optional metadata is accepted; malformed required position data rejects the batch and consumes the conservative reservation.
