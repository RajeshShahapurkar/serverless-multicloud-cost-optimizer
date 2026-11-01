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

## 8. Second UI reduction — direct route allow-list committed

File changed: `ngui/ui/src/utils/routes/index.ts`.

The route registry now explicitly registers only:
- Authentication, invitation, registration, password recovery, email verification and first-run organization setup.
- Home/dashboard.
- Cloud data-source list, details and create/connect routes.
- Expenses, cloud expenses, pool expenses and owner expenses.
- Cross-cloud cost comparison.
- Resources, resource details, resource perspectives and cluster types used by resource navigation.
- Recommendations.
- Basic settings, organization options and theme settings.
- The not-found fallback.

The registry no longer registers direct routes for ML workloads, BI exports, Jira/Slack connection pages, Kubernetes rightsizing, booking/calendar/environment workflows, power schedules, anomaly pages, tagging policy administration, and other unrelated feature pages. Their source files remain in the repository; this is route gating, not source deletion.

A follow-up inspection found that the Resources menu marks cluster-type paths as active and the Expenses menu recognizes pool-expense paths. Those routes were retained in the final allow-list to avoid breaking the retained navigation.

## 9. Important remaining caveats

- This route allow-list has not yet been built or browser-tested locally.
- Some shared UI/API modules still import Jira Bus actions and many feature action creators. They have not been removed because their references must be traced before changing the application bootstrap.
- Some feature routes may be opened by internal links from retained pages. The local smoke test must exercise dashboard, data-source create/detail, expenses (including pool/cloud breakdown), resource details/perspectives, recommendations, settings, login and first-run setup.
- A route hidden from the registry will fall through to the not-found route; this is intentional for excluded MVP pages but should be checked against any retained page links.

## 10. Third UI/API reduction — Jira Bus state wiring removed

The retained MVP UI no longer registers Jira connection routes or shows Jira navigation. The central store and API surface previously still initialized Jira Bus state even after those pages were removed.

The following changes are now committed:
- `ngui/ui/src/reducers.ts`: removed the Jira Bus reducer and its persisted-state handling from the root store.
- `ngui/ui/src/api/index.ts`: removed the Jira Bus action imports/exports and the Jira Bus reducer constant export.
- The dedicated Jira Bus source modules remain in the repository; this is not a destructive source deletion.

A repository code search for `JIRA_BUS`, `getJiraOrganizationStatus`, `updateUserAssignment`, `jira_bus`, and `slacker` returned no additional indexed matches after the central exports were removed. This is useful evidence, but it is not a substitute for a full local TypeScript build and runtime test.

## 11. Route registry regression test

The existing `ngui/ui/src/utils/routes/index.test.ts` checks that:
- Login, registration, password recovery, email verification and cloud-account onboarding remain registered.
- Dashboard, expenses (including cloud/pool/owner breakdowns), cross-cloud comparison, resources and recommendations remain registered.
- ML, BI, Jira/Slack, Kubernetes rightsizing, power scheduling, environment and anomaly routes are not registered.

This test is present in the branch. It still needs to be executed in the user's/local CI environment; source inspection alone does not establish that it passes.

## 12. Fourth reduction audit — Jira / Slack Compose dependency graph

Files inspected on this branch:
- `optscale-deploy/compose/docker-compose.unified.yml`
- `optscale-deploy/compose/nginx.conf`
- `ngui/ui/src/components/App/App.tsx`
- `ngui/ui/src/store.ts`
- `ngui/ui/src/reducers.ts`
- `ngui/ui/src/api/index.ts`

Confirmed remaining deployment references:
- `ngui` still sets `SLACKER_ENDPOINT` and has `depends_on` entries for `slacker` and `jira-bus`.
- `edge` still depends on `slacker`, `jira-bus`, and `jira-ui`.
- nginx still proxies `/slacker/`, `/jira_bus/`, and `/jira_ui/`.
- `jira-ui` depends on `jira-bus`.
- `slacker-executor` depends on `slacker`.

The inspected UI bootstrap/store/reducer/API-index files no longer contain direct Jira/Slack references. The route allow-list also excludes the Jira and Slack connection pages. However, this is not yet a full repository-wide proof that no retained component calls the Slack endpoint.

**Decision:** do not remove or profile these services in this pass. Removing a service while leaving a Compose `depends_on` entry makes the Compose graph invalid, and removing the dependency before confirming all runtime callers could leave a hidden feature broken. Keep the services and nginx routes until the remaining UI source references and any worker/queue consumers are checked. This audit is source inspection only; no Compose validation or runtime test has been run.

Next: trace the retained Recommendations and Resources pages into their REST API endpoints and background workers. This will establish the minimum backend service set before making any further Compose changes.

## 13. Fifth reduction audit — retained resource and recommendation dependencies

The retained UI components were inspected to identify what the MVP backend must continue serving.

### Resources and resource details
- `Resources.tsx` composes expense breakdown, resource-count breakdown, tag/meta breakdown, date-range controls and expense summary containers.
- `Resource.tsx` uses resource details, resource expenses, resource recommendations, allowed-action checks and resource metrics. It also contains environment/booking-related components; those are shared/conditional UI elements and must be traced before being removed.
- `ResourceRecommendations.tsx` renders active and dismissed recommendation modules and calls resource-visibility actions.
- Resource list/detail therefore depends on more than the generic resource CRUD endpoint: retain expense queries, resource metrics/metadata and permissions while this UI remains in scope.

### Recommendations
- `RecommendationDetailsService.ts` calls `getOptimizationDetails(organizationId, { type, status, limit, cloudAccountIds })`, then retrieves allowed actions for resource IDs returned by the recommendation.
- It also calls `updateResourceVisibility` to dismiss/reactivate a recommendation for a resource.
- `RecommendationsCard.tsx` links the dashboard to the full recommendations page and distinguishes cost, security and critical categories.

**Decision:** keep the optimization/recommendation REST endpoints, resource allowed-action endpoint, resource visibility update endpoint, and the backend workers/providers that generate the recommendation data. Do not remove RISP, traffic, resource discovery, or related processing based only on their feature names. Recommendation types may rely on provider-specific data and recommendation classes.

### Expense/dashboard dependencies
- `OrganizationExpenses.tsx` displays last-month, this-month and forecast expense data and links to pool expense breakdown.
- The retained expense dashboard and resources pages therefore require historical/forecast expense APIs and ClickHouse-backed clean expense data; do not remove Metroculus/analytics or expense processing until their exact calls and data sources are traced.

This audit identifies UI-to-API calls and data requirements, not the complete worker implementation graph. The next backend pass should map the exact REST handler methods for optimization details, resource permissions/visibility, resource metrics and expense breakdowns to their controllers and worker queues. No runtime validation has been performed.


## 14. Sixth audit — unified Compose MVP startup inventory

The unified Compose file defines 76 services and 9 named volumes. The existing MVP overlay assigns 18 independent optional workloads to the `extended` profile, leaving 58 services in the default service inventory before dependency/profile resolution.

### Confirmed optional workloads already excluded

- Gemini AI workers and scheduler.
- BI exporter and scheduler.
- Booking and calendar observers and schedulers.
- Organization-violation workers and scheduler.
- Power-schedule worker and scheduler.
- Live-demo generator worker and scheduler.
- Demo organization cleanup and dataset generators.

The overlay changes only Compose profiles. It does not delete their source code, database volumes, API handlers or migrations.

### Services that remain provisionally required

- **Data stores and messaging:** etcd, MariaDB, MongoDB, RabbitMQ, Redis, InfluxDB, ClickHouse and MinIO.
- **Bootstrap and application entry points:** configurator, auth, REST API, ngui and edge.
- **Billing import:** report-import schedulers, diworker, diworker-raw and diworker-clean.
- **Cost data and analytics:** ClickHouse-backed expense queries, Metroculus API/worker/scheduler and required expense-processing services.
- **Resources and recommendations:** resource discovery, resource observation, resource metrics/permissions, optimization endpoints, RISP and traffic processing pending full caller/queue mapping.
- **Shared platform paths:** Herald, Keeper, Katara, Insider, Diproxy, Subspector and other services still referenced by the edge/UI deployment graph.

### Next safe reduction boundary

The next meaningful reduction is not another arbitrary worker profile. It is a coordinated edge/API reduction:
1. Map each retained UI route to its actual REST/API and proxy paths.
2. Identify services used exclusively by routes removed from the MVP.
3. Remove those routes from nginx and the edge dependency graph together.
4. Confirm no retained UI module, background queue consumer or scheduled task calls the service.
5. Run the UI test/build and Compose validation before committing the removal.

### Validation status

- Local user confirmed `docker compose -f docker-compose.unified.yml -f docker-compose.mvp.override.yml config -q` passed.
- This validates Compose syntax and merged configuration only; it does not prove services build, start or pass health checks.
- No backend services, API handlers, database volumes or cloud provider adapters were deleted in this audit.
