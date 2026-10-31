# MVP Backend Feature Reduction Map

Branch: `feature/reduced-cost-optimizer-scope`

This map records source-level evidence gathered before removing backend APIs or runtime services. It is intentionally conservative: the project must continue to import real AWS, Azure and GCP billing, normalize expenses, expose historical cost data, and support resource recommendations.

## 1. Confirmed core billing task path

The current implementation is a three-stage RabbitMQ pipeline:

1. REST API `ReportImportBaseController.create()` creates a report-import record and publishes a task to the `report-imports` queue on the `billing-reports` exchange.
2. `diworker` (`OrchestratorWorker`) validates the report-import request and publishes work to `report-raw`.
3. `diworker-raw` (`RawWorker`) downloads/reads billing files or calls provider APIs, writes raw expenses, and publishes work to `report-clean`.
4. `diworker-clean` (`CleanWorker`) generates clean expense records, updates import/account timestamps, processes alerts, and marks the import completed.
5. Clean expenses are stored through the ClickHouse client; raw expenses and import/report metadata use MongoDB. REST API and UI query the normalized expense data.

**Decision:** keep RabbitMQ, REST API, MongoDB, ClickHouse, and all three diworker services. Do not combine or remove any stage in the first MVP reduction.

Relevant source:
- `rest_api/rest_api_server/controllers/report_import.py`
- `diworker/diworker/main.py`
- `diworker/diworker/raw_worker.py`
- `diworker/diworker/clean_worker.py`
- `diworker/diworker/worker_base.py`

## 2. Provider-specific post-import processing

The clean worker calls importer hooks for traffic and RISP processing after generating clean records. The base importer implementations are no-ops, but provider implementations override them:

| Provider | Traffic task hook | RISP task hook |
|---|---:|---:|
| AWS | Yes | Yes |
| Azure | Yes | Yes |
| GCP | Yes | No override found in the importer scan |
| Alibaba | Yes | No override found in the importer scan |

AWS and Azure call both base task-creation implementations. GCP and Alibaba call traffic task creation. The corresponding processing services must not be removed until their task consumers and selected recommendation pages are fully mapped.

**Decision:** retain `risp-worker`, `risp-scheduler`, `trapper-worker`, and `trapper-scheduler` provisionally. Do not assume that RISP/traffic are unrelated to the cloud-cost MVP.

## 3. Features already excluded from default Compose startup

The separate `docker-compose.mvp.override.yml` puts the following workloads into the `extended` profile:

- Gemini / AI background workers and scheduler.
- BI export worker and scheduler.
- Booking and calendar observer workers and schedulers.
- Organization-violation workers and scheduler.
- Power-schedule worker and scheduler.
- Live-demo generator worker and scheduler.
- Demo organization cleanup and dataset generators.

These are excluded from the default MVP startup only; source code and upstream Compose definitions remain intact. They can be opted into with the `extended` profile.

## 4. Feature families not yet safe to remove

### Jira and Slack
The left navigation no longer exposes their feature pages, but:
- `ngui` still declares runtime dependencies on `slacker` and `jira-bus`.
- `edge` still declares dependencies on `slacker`, `jira-bus`, and `jira-ui`.
- The UI API index still imports Jira Bus actions/reducer and exports Jira organization status.
- The nginx config still routes `/slacker/`, `/jira_bus/`, and `/jira_ui/`.

**Decision:** do not profile or remove these services yet. A safe removal needs coordinated UI API initialization, Compose dependency, environment, and nginx changes plus a frontend build/test.

### Insider / governance
The edge proxy routes `/insider/` to `insider-api`. Do not remove it until the retained UI and REST API paths are checked for calls into that service.

### Metroculus / analytics
The UI and edge have a dedicated metroculus path. Historical cost dashboard dependencies need to be checked before removing analytics services.

### Resource discovery / recommendations
Keep resource discovery worker and scheduler. Keep the resource observer and violation paths provisionally until recommendation pages are traced end-to-end.

### Herald / Keeper / notifications and reports
The UI and edge explicitly depend on Herald API and Keeper. Keep them until notification and report download paths are verified without them.

## 5. API surface reduction: defer deletion

The UI's central API module (`ngui/ui/src/api/index.ts`) imports and re-exports many unrelated action creators, including ML, Gemini, BI, environment booking, calendar, power schedule, and Jira status functions. A menu-only change does not remove those imports or guarantee those pages cannot be reached by a direct URL.

The central REST API handler registration also includes many routes. Removing handlers before the route registry and UI callers are mapped can break imports or runtime initialization.

**Decision:** do not delete API handlers or UI API modules in this pass. First gate direct routes and remove feature API imports only when there are no retained callers. Preserve common auth, cloud account, expenses, resources and recommendation endpoints.

## 6. Next safe reduction tasks

1. Inspect the exact route registry and identify pages belonging exclusively to excluded features.
2. Inspect the initialization/API bootstrap path for Jira and Slack calls.
3. Inspect recommendation page data calls to determine the required resource, RISP, traffic and analytics services.
4. Add tests for the reduced menu and any route guards.
5. Only then update Compose dependencies and nginx locations for a feature family.
6. Validate with a frontend production build and Compose config before any local startup.

## 7. Validation limitations

- This is a source inspection, not a runtime integration test.
- The current GitHub-connected workflow can commit source changes, but cannot run Docker on the user's Windows machine.
- The Compose overlay has not yet been checked with the user's local Docker Compose version.
- No API routes, DB schemas, migrations, importer code or original Compose services have been deleted.
