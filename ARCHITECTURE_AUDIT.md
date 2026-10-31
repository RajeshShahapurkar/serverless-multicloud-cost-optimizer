# Architecture Audit — Reduced Multi-Cloud Cost Optimizer

Branch: `feature/reduced-cost-optimizer-scope`

This audit records verified source findings from the current branch. It deliberately separates billing ingestion from cloud resource discovery and from OptScale's platform-wide supporting services.

## 1. Billing import path (verified)

The repository's report-import processing is a three-stage asynchronous pipeline:

1. **Orchestrator** — `diworker/diworker/main.py` validates the report-import request, checks account/organization state, resolves the importer via `get_importer_class`, and publishes work to the raw queue.
2. **Raw worker** — `diworker/diworker/raw_worker.py` loads the selected importer and executes either file-based report processing or API/manual processing. It publishes the clean queue task when raw ingestion finishes.
3. **Clean worker** — `diworker/diworker/clean_worker.py` generates normalized clean expense records, updates account import time/configuration, processes alerts, and schedules traffic/RIsp processing tasks.

The three worker processes are exposed as separate Compose services: `diworker`, `diworker-raw`, and `diworker-clean`. They share the same application image in unified mode but are separate long-running processes. They are not safe to collapse into one service without changing worker/queue behavior.

### Importer routing

`diworker/diworker/importers/factory.py` currently maps these cloud types:

| Cloud type | Importer | Mode |
|---|---|---|
| `aws_cnr` | `AWSReportImporter` | CSV/report-file |
| `azure_cnr` | `AzureApiImporter` | API-based, with usage schemes |
| `azure_cnr` + `export` | `AzureExportImporter` | Export file |
| `gcp_cnr` | `GcpReportImporter` | Report-file |
| `alibaba_cnr` | `AlibabaReportImporter` | Report-file |
| `kubernetes_cnr` | `KubernetesReportImporter` | Report-file |
| `nebius` | `NebiusReportImporter` | Report-file |
| `environment` | `EnvironmentReportImporter` | Internal/manual |
| `databricks` | `DatabricksReportImporter` | Provider-specific |

The AWS importer inherits `CSVBaseReportImporter` and handles CUR-style CSV/Parquet report data. Azure has a direct Consumption API importer path plus an export-file path. Important correction from the follow-up source inspection: GCP's `GcpReportImporter` inherits `BaseReportImporter` and its `load_raw_data()` calls the adapter's `get_usage()` method, which queries the configured BigQuery billing export table. So GCP ingestion is query-based against a preconfigured BigQuery export, not a report-file importer. The detailed provider credential and billing setup is documented in `CLOUD_CREDENTIAL_SETUP.md`.

### Important product implication

A cloud adapter is not equivalent to a working billing integration. For the MVP, the provider onboarding and report/export acquisition steps must be tested end-to-end for each provider. Existing source support can process billing data, but it does not prove that a newly linked account will immediately stream billing data from a live API.

## 2. Cloud adapters and discovery

The adapter package includes dedicated AWS, Azure, and GCP modules:

- `tools/cloud_adapter/clouds/aws.py`
- `tools/cloud_adapter/clouds/azure.py`
- `tools/cloud_adapter/clouds/gcp.py`

The adapters include resource/service APIs as well as billing-related functionality. The package manifest also installs libraries for Alibaba, Nebius, and Databricks. Those unrelated SDK dependencies should be candidates for a later optional-dependency split, not removed before all imports and runtime paths are mapped.

## 3. Unified Compose deployment inventory

The current `optscale-deploy/compose/docker-compose.unified.yml` contains **76 services**. It is a unified application-image deployment, not a 76-to-small-stack reduction. It still runs independent API processes, workers, schedulers, databases, queues, object storage, metrics services, and an edge proxy.

### Data and infrastructure layer

- etcd, MariaDB, MongoDB, RabbitMQ, Redis, InfluxDB, ClickHouse, MinIO
- Thanos receive, store gateway, and query

These are not interchangeable. For example, the import pipeline explicitly relies on RabbitMQ queues, MongoDB raw/resource data, ClickHouse expenses, and etcd-backed configuration. The Compose worker definitions also explicitly depend on healthy REST API and ClickHouse services.

### Main app and user-facing layer

- REST API and authentication
- Keeper, Herald API/engine, Katara, Insider API, Slacker
- Metroculus API, Jira bus/UI, DIP proxy, Subspector
- Next/UI service (`ngui`) and nginx edge proxy

The current UI's dependency graph includes several services beyond the REST API and auth. Removing them based on feature names alone can break routes, notifications, or page loading.

### Billing and cost processing layer

- `diworker`, `diworker-raw`, `diworker-clean`
- report-import schedulers (15-minute, hourly, 6-hour, 24-hour variants)
- `bumischeduler` and `bumiworker`

These are central to actual billing ingestion and processing and should be retained in any reduced billing MVP unless an equivalent replacement is deliberately implemented.

### Candidate optional feature families (not yet approved for removal)

- Jira integration: `jira-bus`, `jira-ui`
- Chat/notification integrations: Slacker and related executors
- IT environment booking/calendar/power scheduling: booking/calendar/power-schedule workers and schedulers
- Resource policy/violation workflows: resource-observer, resource-violations, organization-violations
- Gemini, BI export, Trapper, RISP, Metroculus analytics, demo/data-generator and cleanup jobs

Some of these have cross-dependencies with the existing UI or platform startup. They are candidates for a controlled feature-profile, not safe immediate deletions.

## 4. Credential separation and security

`optscale-deploy/overlay/user_template.yml` labels `service_credentials` as credentials used to retrieve cloud pricing information for recommendations. These are platform/service credentials and are distinct from the credentials each customer supplies to connect their cloud account.

The GCP pricing configuration refers to BigQuery pricing export and permissions such as `bigquery.jobs.create` and `bigquery.tables.getData`. This should not be mistaken for the customer's billing export ingestion configuration.

Never commit real cloud credentials, service-account private keys, generated `.env` files, or personal access tokens. The checked-in template contains placeholders; use local secret configuration for real values.

## 5. Deployment constraints and reduction strategy

The Compose quickstart states that it is a near-full evaluation/development deployment, not production, and recommends 8 CPU cores, 16 GB RAM (32 GB recommended), and 40 GB free disk. It also describes 60+ services.

The unified Compose file contains 76 services. A single shared app image reduces the number of application images to build/pull; it does not remove the memory/CPU cost of running the processes.

Given the project's 16 GB Windows laptop and the WSL/Docker memory budget previously observed at about 7.6 GiB, do not run this full stack as the next step.

### Safe reduction plan

1. Retain the real billing import chain and its datastore/queue dependencies.
2. Trace all REST API route dependencies for the existing UI before removing application services.
3. Trace the UI routes/features that will be retained; preserve the UI appearance.
4. Identify optional feature groups and their complete dependency closure.
5. Create a separate MVP Compose profile/file rather than overwriting the upstream unified or default Compose files.
6. Run static Compose validation and targeted tests before the user starts Docker.
7. Only then ask the user to reinstall Docker Desktop and run the reduced stack.

## 6. Current conclusions

- AWS, Azure, and GCP code paths exist, but their ingestion mechanisms differ.
- AWS and GCP currently use report-file importer paths; Azure supports both Consumption API and export-file modes.
- Billing processing is a queue-based three-worker pipeline; all three stages are required for the current design.
- The current unified Compose file has 76 services and is not suitable for this laptop's available WSL memory as-is.
- The next code change should be a separate reduced MVP deployment profile after route/service dependency tracing. No existing services should be deleted yet.

## 7. Next audit tasks

- [ ] Map the report-import scheduler and cloud-account onboarding endpoints for AWS/Azure/GCP.
- [ ] Identify exact API and service dependencies of the current UI and edge proxy.
- [ ] Trace the minimum set of services required for auth, cloud account management, billing import, expense queries, and dashboard pages.
- [ ] Produce a candidate reduced Compose file with a documented dependency rationale.
- [ ] Validate YAML/Compose config and run relevant importer/worker tests.
