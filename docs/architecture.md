# Architecture

```text
MockProvider -> backend policy / SQLite -> GET /api/v1/display
                                             |          |
                                      desktop PNG   ESP32-S3 / Wokwi
                                                     Display interface
                                                     SerialDisplay now
                                                     Waveshare later
```

The ESP32 only calls our backend. Live FR24 is an unimplemented future adapter to the Provider protocol. Unknown provider modes fail startup. Fixtures are synthetic normalized provider-boundary records, not assertions about FR24 wire format. A future adapter must validate actual responses and bound result counts before enabling network access.

## Implemented policy
- A validated private timezone and weekday/weekend windows control schedule enforcement. Public defaults use UTC and synthetic demo hours. Outside these windows the provider is not invoked; zoneinfo handles DST.
- Demand-driven refresh once per UTC-aligned five-minute slot while active. There is no background job; if no device asks, no poll occurs. Client wake guidance points to the next active slot. Requests inside a slot share the saved result; clients cannot force upstream refresh.
- SQLite transaction reserves credits and marks the slot before invoking provider. Other callers can briefly receive an error placeholder during an in-progress fetch; no second request is launched. Restart preserves both usage and slot. Single backend process is the deployment target; SQLite also serializes local concurrent reservations. No network filesystems.
- Center, airport and radius come from validated deployment configuration. Local filtering precedes ranking: configured-airport inbound, configured-airport outbound, then nearest other aircraft; distance and ID break ties. “Interesting” currently means nearest, not aircraft type.
- Metadata cached by flight ID for six hours; only missing fields are filled. No paid metadata calls exist. TTL refresh on seen records is sliding. Future maintenance must prune old rows.
- Provider failures return error, with no stale flight retained. Firmware retains its previous screen on transport/protocol failure. API stale is reserved for future retention behavior and currently false. No retries within a slot.
- Mock ledger uses a conservative synthetic 120-credit reservation for every fixture request (20×6); failed/empty calls keep that reservation. This tests protection, not realistic FR24 consumption. No refunds or claim of actual billing reconciliation.

## Budget design and unresolved tradeoff
For an illustrative 3,000 polls/month, one Light result per poll at 6 credits costs 18,000; one hypothetical 2-credit enrichment per poll adds 6,000. The 24,000 total is a model, not measured usage. Actual viewing windows, empty responses, metadata hit rate and endpoint costs must be validated privately. Two results every poll can exceed the target before enrichment.

A one-result discovery query cannot guarantee global inbound > outbound priority. This implementation ranks every mock candidate; the future live discovery strategy must explicitly choose between limited discovery, airport-filtered queries and additional cost. Do not silently issue three priority queries per slot.

Current cap is 25,000, leaving 5,000 under the user's normal 30,000 allowance. Hard stop, no top-up and no automatic off-schedule/manual bypass. Calendar UTC month reset is a POC placeholder: actual subscription billing-cycle reset and durable reconciliation are mandatory before live access. Ledger is local to this application; outside usage of a future shared API key is not accounted for. A dedicated key/account usage reconciliation is a live-phase gate.

## Decisions needing review
1. Confirm privately configured center/radius and whether nearest is a useful fallback.
2. Accept best-priority-among-returned candidates or fund broader discovery.
3. Confirm hard stop at 25k and service behavior when the daily/monthly trajectory is high; 20k is a planning goal, not a lower spending requirement.
4. Confirm demand-driven polling versus a future single scheduled collector.
5. Before live mode: implement pre-call active-window recheck, network timeouts, bounded query costs, provider error normalization, billing-period config and reconciliation. No live safety claim is made for this mock scaffold.
6. Before remote deployment: TLS and device authentication, bounded streaming response parsing, log retention, and data caching/redistribution terms review. Local POC binds loopback; firmware HTTP is for trusted mock development only.
7. Display selection, battery/runtime target and enclosure dimensions remain deliberately open.

## Official references checked 2026-09-26
- https://fr24api.flightradar24.com/subscriptions-and-credits (normal Explorer 30k)
- https://fr24api.flightradar24.com/docs/credit-overview (Light per-result costs; recheck before live)
- https://docs.wokwi.com/guides/esp32-wifi (private gateway / host.wokwi.internal)
- https://docs.wokwi.com/vscode/project-config (firmware/ELF configuration)
