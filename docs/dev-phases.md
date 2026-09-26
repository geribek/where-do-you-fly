# Development phases
Only Phase 0/1 is authorized in this delivery. Each gate must pass before advancing.

| Phase | Work | Acceptance / test gate |
|---|---|---|
| Pre-publication security | Private env/runtime settings, synthetic public fixtures, staged-content guard and CI scanner | All public candidate and staged-file scans pass; no credentials/personal geography/tracker links in source; no commit or push before this gate |
| 0 — Decisions | Contract, schedule, budget model, geography and ranking | Review open decisions in architecture.md; use standard 30,000 allowance, never promotional credits |
| 1 — Mocks (this scaffold) | FastAPI, SQLite, seven fixtures, serial firmware interface | Tests pass for schedule/DST, deterministic priority, malformed data, caching, shared polls, restart and budget stop; live mode rejected |
| 2 — Desktop preview | Develop 800×480 layout for all statuses, long/missing names | Golden images reviewed; exact white/black/red/yellow palette; text fits all seven fixtures |
| 3 — Wokwi | Build S3 firmware, run against local mock backend via gateway | All statuses readable in Serial; Wi-Fi loss/reconnect, timeout, invalid JSON, server restart and long sleep tested; zero FR24 traffic |
| 4 — Live FR24 logging | Explicit review first; implement bounded provider and logging without hardware | Verify endpoint/cost/schema/terms and billing reset; 7–14 days of active-window logs; zero off-window calls; projected 20k–25k/month; reservations survive crashes; prove timeout/rate-limit/budget behavior |
| 5 — Real ESP32 | Use an available S3 board with SerialDisplay | 72-hour soak; reconnects and backend outage recovery; timestamps/scheduling correct; no direct FR24 access |
| 6 — Battery | Measure wake/Wi-Fi/sleep energy, choose power system from measurements | Agreed runtime demonstrated from measured duty cycle, safe charging design reviewed; no guessed capacity or premature purchase |
| 7 — E-paper | Select exact four-color 800×480 panel and implement WaveshareEpaperDisplay | Verify voltage, pinout, refresh time, ghosting and energy; palette/layout test; driver swaps without provider changes |
| 8 — Enclosure | Design around measured final hardware | Fit/connector access/thermal and battery clearance verified with cheap prototype, then final print |

Stop here before live FR24 implementation. Phase 2/3 execution is also future work; configuration and test instructions are supplied now.
