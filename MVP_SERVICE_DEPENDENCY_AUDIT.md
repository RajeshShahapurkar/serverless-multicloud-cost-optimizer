# MVP Service Dependency Audit

Branch: `feature/reduced-cost-optimizer-scope`

This audit combines the unified Compose service definitions, the nginx path map, the REST API route registration, and the current UI route/menu wiring. It is used to decide what can be disabled safely without changing the visible UI or breaking the billing pipeline.

## 1. Important deployment facts

- `docker-compose.unified.yml` defines 76 services.
- The unified image reduces first-party application image count; it does not combine the services into one process.
- The Compose quickstart is explicitly a near-full evaluation/development deployment. Its documented minimum is 8 CPU cores, 16 GB RAM and 40 GB free disk.
- The edge nginx configuration proxies separate URL prefixes to several independent backend services.
- The UI's `ngui` service declares dependencies on REST API, auth, keeper, slacker, Redis, Herald API and Jira bus.
- The REST API imports the v2 handler package at startup. The v2 package imports a broad set of handler modules, and `server.py` registers a large route table.

These facts mean that simply deleting services from Compose or removing API modules is not a safe first optimization.

## 2. MVP user journeys to preserve

The initial reduced product is intended to preserve:
1. User registration/login and authenticated session.
2. Organization context.
3. Cloud data-source list, create, verify and update.
4. AWS, Azure and GCP billing import scheduling/status.
5. Normalized expense history, totals and breakdowns.
6. The existing dashboard and data-source UI appearance.
7. Basic resource discovery/recommendation functionality only where it is already required by the selected UI and onboarding flow.

The MVP must not silently replace real cloud billing with sample/live-demo data.

## 3. Core services — retain in the first candidate profile

| Service | Reason to retain |
|---|---|
| `etcd-client` | Shared runtime configuration for the app and workers |
| `mariadb` | Relational application data used by the platform |
| `mongo` | Raw expense/report/resource document storage |
| `rabbitmq` | Billing task queues and application task messaging |
| `redis` | Explicit ngui dependency and UI/server state/cache |
| `clickhouse` | Clean expense storage/query path; used by billing workers and REST API |
| `minio` | Bootstrap dependency and report upload/import object storage |
| `configurator` | Required one-shot bootstrap for etcd and supporting services |
| `auth` | UI authentication endpoint |
| `restapi` | Cloud accounts, imports, expense and dashboard API |
| `herald-api` | Explicit REST API and UI dependency |
| `herald-engine` | Keep provisionally until activity/notification task flow is proven unnecessary |
| `keeper` | Explicit UI dependency and `/report/` proxy route |
| `slacker` | Explicit UI dependency in current Compose, even if Slack integration is hidden |
| `jira-bus` | Explicit UI dependency in current Compose, even if Jira UI is hidden |
| `ngui` | Existing UI; preserve visual design |
| `edge` | Existing nginx entry point and path-based routing |
| `diworker` | Billing import orchestrator |
| `diworker-raw` | Raw billing data ingestion |
| `diworker-clean` | Normalization and clean-expense generation |

This is a conservative keep-list, not yet a minimal runnable stack. Several services may be removable after code-level call-path tests and UI dependency changes, but they should not be removed just because their product feature is out of MVP scope.

## 4. Conditional services — keep until a specific path is tested

| Service/group | Why it is conditional |
|---|---|
| `influxdb` | Configurator expects it; some app telemetry/metrics paths may rely on it |
| `thanos-receive`, `thanos-storegateway`, `thanos-query` | `diproxy` depends on Thanos receive; retain if current UI/API uses storage/metrics paths |
| `diproxy` | Edge exposes `/storage/`; resource/metrics paths may use it |
| `katara` | Edge exposes `/katara/`; check UI route calls before excluding |
| `insider-api` | Edge exposes `/insider/`; check retained pages |
| `subspector` | Edge exposes `/subspector/`; check UI route calls |
| `bumiworker`, `bumischeduler` | Initial-import completion schedules checklist processing; test whether onboarding/dashboard expects it |
| `resource-discovery-worker` and scheduler | Needed if recommendations/resource inventory are retained |
| `resource-observer-worker` and scheduler | Needed only for observer/anomaly workflows |
| `risp-worker`, `risp-scheduler` | Clean worker triggers downstream RI/SP processing; inspect exact MVP dashboard dependencies |
| `metroculusapi`, `metroculus-worker`, scheduler | Analytics/metrics path; retain only if selected dashboard pages call it |
| `trapper-worker`, `trapper-scheduler` | Inspect event/usage tracking path before exclusion |
| `herald-executor`, `keeper-executor` | Async event/report work; inspect which retained routes publish tasks |
| `katara-worker`, `insider-worker` | Keep only if their API/service functions are used by retained UI paths |

## 5. First candidates for exclusion from the MVP runtime

These are product feature groups, not approved deletions. Exclude only after the associated UI links/routes and API calls are disabled or verified unused.

- Jira UI and external Jira integration: `jira-ui`, and possibly `jira-bus` after removing the UI's hard dependency and checking integration actions.
- Slack integration: hide Slack connection routes/actions and then assess `slacker` and its executor.
- ML/AI workloads: `gemini-worker`, `gemini-data-worker`, `gemini-scheduler`, and ML-specific pages/APIs.
- BI export: `bi-exporter`, `bi-scheduler`, and BI export routes/pages.
- Kubernetes-specific rightsizing: K8s pages and associated processing if K8s is explicitly out of MVP scope.
- Environment booking/power scheduling/calendar: related workers and schedulers, after removing those routes/pages.
- Demo and sample-data generation: `live-demo-generator-worker`, `live-demo-generator-scheduler`, `demo-org-cleanup`, `failed-imports-dataset-generator`, `users-dataset-generator`, provided real-account onboarding and tests do not require them.
- Maintenance jobs: `cleanmongodb`, `cleaninfluxdb`, `layout-cleaner` may be deferred for a short local evaluation, but data growth and cleanup implications must be documented.

## 6. Why API reduction is not a Compose-only task

- `rest_api_server/handlers/v2/__init__.py` imports many handler modules.
- `rest_api_server/server.py` explicitly registers routes for data sources, cloud account verification, report scheduling, expenses, recommendations, resources and many unrelated features.
- The UI's route registry imports a broad set of pages, and its main menu includes many product areas.
- The UI currently makes calls to the REST API, auth API, Jira bus, Keeper and Slacker endpoints.

Therefore, the safest initial profile should keep the existing REST API and UI intact. We should reduce background workers/schedulers only after tracing which tasks are published by the retained onboarding and billing flows. Hiding a menu item alone does not remove backend dependencies.

## 7. Candidate reduction strategy

### Stage A — no source-code deletion
Create a separate Compose override/profile for an evaluation stack. Keep the existing `docker-compose.yml` and `docker-compose.unified.yml` unchanged. First disable clearly optional schedulers/workers that are not invoked by the billing/dashboard flow, then validate dependency closure.

### Stage B — UI feature gating
Preserve current styling and layout. Hide only out-of-scope menu items/routes. Before disabling an API or service, search all UI and server references and test the retained pages.

### Stage C — billing-only backend
Retain the complete account onboarding, import scheduling, raw import, clean generation and expense query path. Trace downstream tasks from clean generation before excluding RISP/traffic or checklist-related services.

### Stage D — validation
For each candidate service exclusion:
1. Search source references and published task/queue names.
2. Check Compose `depends_on`, environment URLs, nginx routes and configurator assumptions.
3. Run `docker compose config` on the new profile.
4. Run unit tests for affected importer/controller paths.
5. Test login, connect cloud account, schedule import, observe import completion and load expense dashboard.
6. Confirm no sample/demo data is being mistaken for real billing.

## 8. Current decision

Do not create a guessed 15-service Compose file yet. The dependency audit shows that UI, edge routing, REST route registration, and several app workers are interconnected. The next concrete task is to map the exact background queue/task dependencies emitted by the retained cloud onboarding and clean-expense paths. Once that is complete, a defensible MVP Compose file can be created without risking the existing UI or live billing flow.
