# MVP Service Dependency Audit

Branch: `feature/reduced-cost-optimizer-scope`

This audit combines the unified Compose service definitions, nginx path routing, REST API route registration and UI navigation wiring. It guides a safe reduction without changing the existing visual design or breaking live billing.

## 1. Deployment facts

- The unified Compose file defines 76 services.
- The unified image reduces the number of first-party application images; it does not combine all services into one process.
- The Compose quickstart documents minimum requirements of 8 CPU cores, 16 GB RAM and 40 GB free disk.
- Nginx routes several URL prefixes to separate backend services.
- The UI service currently declares dependencies on REST API, auth, Keeper, Slacker, Redis, Herald API and Jira Bus.
- The REST API imports a broad v2 handler package and registers many routes.

Do not delete services based only on whether a feature is visible in the menu.

## 2. MVP scope

Preserve:
1. Login and authenticated sessions.
2. Organization context.
3. Connect, verify and manage AWS, Azure and GCP cloud accounts.
4. Billing import scheduling and status.
5. Normalized expenses, historical trends and breakdowns.
6. Existing dashboard and data-source UI styling.
7. Resource inventory and cost visibility.
8. Idle-resource and rightsizing recommendations where supported by the retained data.
9. Cross-cloud cost comparison and estimated savings.

Exclude from the first MVP:
- Kubernetes cost allocation/rightsizing.
- ML/AI/ML Ops tools.
- Jira and Slack integrations.
- BI exports.
- Environment booking, power schedules and calendar workflows.
- Advanced enterprise governance, chargeback and unrelated collaboration features.
- Demo/sample-data generation in the real-billing user journey.

## 3. First UI reduction — committed

File changed: `ngui/ui/src/utils/menus/mainMenu.tsx`

The left navigation now includes only:
- Home
- Recommendations
- Resources
- Expenses / Cost Explorer
- Cloud Cost Comparison
- Data Sources
- Settings

This is deliberately a navigation-only first pass. It does not delete routes, API handlers, workers or service definitions. Existing route files remain available for rollback and dependency inspection. The original UI components and styling were not redesigned.

## 4. Services — conservative keep-list

| Service | Reason |
|---|---|
| `etcd-client` | Shared runtime configuration |
| `mariadb` | Relational application data |
| `mongo` | Raw expense/report/resource document storage |
| `rabbitmq` | Task queues and messaging |
| `redis` | Explicit UI dependency and cache/state |
| `clickhouse` | Clean expense storage/query path |
| `minio` | Bootstrap and report/object storage |
| `configurator` | One-shot bootstrap |
| `auth` | UI authentication |
| `restapi` | Cloud accounts, imports, expenses and dashboard API |
| `herald-api` | Explicit REST API and UI dependency |
| `keeper` | Explicit UI dependency and report proxy |
| `slacker` | Explicit UI dependency in current Compose |
| `jira-bus` | Explicit UI dependency in current Compose |
| `ngui` | Existing user interface |
| `edge` | Existing nginx entry point |
| `diworker` | Import orchestration |
| `diworker-raw` | Raw billing ingestion |
| `diworker-clean` | Normalization and clean expense generation |

This is not yet a minimal runnable list. It is a safe starting point for dependency tracing.

## 5. Conditional services

Keep these until the retained code paths are traced:
- `influxdb`: configurator expects it; metrics paths may depend on it.
- `thanos-receive`, `thanos-storegateway`, `thanos-query`: `diproxy` depends on Thanos receive.
- `diproxy`: edge exposes `/storage/`.
- `katara`, `insider-api`, `subspector`: separate edge routes exist.
- `bumiworker`, `bumischeduler`: check whether onboarding/dashboard flow schedules checklist work.
- Resource discovery and observer workers/schedulers: needed if resource inventory/recommendations are retained.
- `risp-worker`, `risp-scheduler`: inspect downstream clean-expense tasks.
- Metroculus, trapper, Herald and Keeper executors: trace selected analytics, event and report flows before exclusion.
- Other workers and schedulers: remove only after proving no retained route/task publishes work for them.

## 6. First exclusion candidates

These are feature groups to gate or disable only after references and dependencies are checked:
- ML/AI: Gemini workers/schedulers and ML pages/APIs.
- Jira and Slack integration: Jira UI/bus and Slacker paths.
- BI export: BI exporter/scheduler and related UI.
- Kubernetes-only features.
- Environment booking, calendar and power scheduling.
- Demo/sample data generators.
- Maintenance/cleanup jobs may be deferred for a short evaluation only with data-growth implications documented.

## 7. Why Compose-only deletion is unsafe

- `rest_api_server/handlers/v2/__init__.py` imports many handler modules.
- `rest_api_server/server.py` explicitly registers many API routes.
- UI routes are imported through a central route registry.
- The UI currently calls REST API, auth, Jira Bus, Keeper and Slacker endpoints.
- Compose service dependencies and nginx routes can cause startup or runtime failures if services are removed without updating their callers.

Therefore, retain the existing REST API and UI for now. Trace the account onboarding, import scheduling, raw import, clean expense and expense-query path before reducing worker services.

## 8. Next steps

1. Trace task/queue names emitted by cloud account verification and import scheduling.
2. Trace raw worker to clean worker to downstream processing and persistence.
3. Trace which dashboard endpoints read clean expense data.
4. Identify which optional services are outside those call paths.
5. Create a separate MVP Compose override/profile. Do not overwrite the upstream Compose files.
6. Validate Compose config, tests, login, cloud connection, import completion and dashboard data before running the reduced deployment.

## 9. Validation status

- UI navigation reduction: committed.
- Visual redesign: none.
- API/route deletion: none.
- Compose/service deletion: none.
- Local build/test: not yet run in this environment.
- Real cloud import test: pending.
