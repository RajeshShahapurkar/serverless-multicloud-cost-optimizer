# Billing Onboarding and Scheduling Flow

Branch: `feature/reduced-cost-optimizer-scope`

This note documents the cloud-account and report-import paths inspected in the current source. It is a source audit, not a statement that the cloud integrations have been tested against live accounts.

## 1. Cloud account onboarding

Relevant source:

- `rest_api/rest_api_server/handlers/v2/cloud_account.py`
- `rest_api/rest_api_server/controllers/cloud_account.py`
- `tools/cloud_adapter/cloud.py`
- `tools/cloud_adapter/clouds/aws.py`
- `tools/cloud_adapter/clouds/azure.py`
- `tools/cloud_adapter/clouds/gcp.py`

The v2 cloud-account collection handler accepts cloud-account creation for an organization and requires the `MANAGE_CLOUD_CREDENTIALS` permission. The request includes a cloud type, a display name, provider config, and optional `auto_import` and `process_recommendations` flags.

The controller:
1. Resolves the adapter class from the requested cloud type.
2. Validates the required provider credential fields against the adapter's `BILLING_CREDS` definitions.
3. Calls the adapter's credential configuration and validation methods.
4. Obtains the provider account identifier and warnings.
5. Checks for duplicate accounts.
6. Configures billing report settings via `_configure_report`.
7. Initializes resource discovery metadata.
8. Persisting the account, creating a default pool/rule, and publishing account-created activity.
9. If `auto_import` is enabled, calls `_schedule_report_import`.

AWS has additional assumed-role handling: if role account/name are supplied, the controller retrieves AWS service credentials from the platform configuration and rejects simultaneously supplied static access key/secret fields. The source includes an external ID validation method.

This confirms that onboarding is adapter-driven and that provider credentials are validated before the account is saved. The exact required fields differ by adapter and should be extracted from each adapter's `BILLING_CREDS` declaration before writing a user-facing setup guide.

## 2. Automatic report import

Relevant source:

- `rest_api/rest_api_server/controllers/cloud_account.py`
- `rest_api/rest_api_server/controllers/report_import.py`
- `rest_api/rest_api_server/handlers/v2/schedule_imports.py`
- `diworker/diworker/main.py`
- `diworker/diworker/raw_worker.py`
- `diworker/diworker/clean_worker.py`

When a cloud account has automatic import enabled, the cloud-account controller schedules an initial report import. The report-import controller publishes a message to the RabbitMQ `billing-reports` direct exchange with routing key `report-imports`.

The v2 schedule-import handler supports:
- Scheduling by period.
- Scheduling by organization, optionally filtered by cloud account type.
- Scheduling a specific cloud account.
- Optional import date range and reimport flag for a specific account.

The handler enforces cluster-secret access for broad scheduled jobs, or `MANAGE_CLOUD_CREDENTIALS` permission when scheduling a specific cloud account.

## 3. Worker queue topology

The billing import pipeline uses a separate exchange/queue flow:

| Stage | Compose service | Queue | Responsibility |
|---|---|---|---|
| Orchestrator | `diworker` | `report-imports` | Validate request, resolve importer, route task |
| Raw ingestion | `diworker-raw` | `report-raw` | Download/process report or call API, write raw expenses |
| Clean generation | `diworker-clean` | `report-clean` | Normalize raw data into clean expenses and finalize import |

The queue constants are defined in `diworker/diworker/worker_base.py`. The same module establishes that workers use etcd configuration, RabbitMQ, MongoDB and ClickHouse clients. The clean stage also calls traffic and RI/SP task creation methods, so those downstream tasks need tracing before any related workers are excluded.

## 4. Import cadence and scheduling

The unified Compose file runs separate report-import scheduler processes for multiple cadence settings: `report-import-scheduler-0`, `report-import-scheduler-1`, `report-import-scheduler-6`, and `report-import-scheduler-24`. The quickstart documentation describes the family as 15-minute / 1-hour / 6-hour / 24-hour variants.

The `bumischeduler` is a separate checklist scheduler. It periodically reads organization checklists and publishes Bumi tasks to the `bumi-tasks` exchange. It is not the same thing as billing report ingestion.

## 5. Implications for MVP reduction

- Keep the cloud-account REST API and its adapter validation path.
- Keep the report-import REST API and scheduler path.
- Keep all three billing worker stages.
- Keep RabbitMQ, etcd, MongoDB, ClickHouse, and the REST API as required by the inspected pipeline.
- Keep MinIO if the selected report-upload/import paths use it; the report-import controller uses MinIO for uploaded report files.
- Do not remove Bumi/checklist functionality until the retained UI and post-first-import workflow have been checked.
- Do not assume the report scheduler variants can be removed until the selected automatic-import cadence is deliberately replaced with a simpler single scheduler and tested.

## 6. Next source audit

- [ ] Extract exact AWS, Azure, and GCP billing credential field definitions.
- [ ] Inspect `_configure_report` for each provider and document the required export/report setup.
- [ ] Inspect report-import scheduler implementation and cadence configuration.
- [ ] Trace API route registration and identify the minimum REST API/UI features.
- [ ] Trace clean-expense downstream task creation to determine whether RISP/traffic workers are required for the MVP dashboard.
