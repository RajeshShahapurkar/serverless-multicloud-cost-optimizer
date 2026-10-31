# Reduced Multi-Cloud Cost Optimizer Scope

This document records the project-specific scope for the `feature/reduced-cost-optimizer-scope` branch. It is an implementation plan, not a claim that the reduced deployment is already working.

## Project objective

Adapt the existing OptScale codebase into a student-project-sized multi-cloud cost optimizer focused on AWS, Microsoft Azure, and Google Cloud Platform (GCP), while preserving the existing OptScale UI unless a change is necessary.

The target capabilities are:

1. Connect supported cloud accounts using least-privilege credentials.
2. Ingest actual billing/cost data for AWS, Azure, and GCP.
3. Normalize and display costs in a unified view.
4. Show historical spending trends and provider comparisons.
5. Surface a limited, explainable set of idle-resource and rightsizing recommendations.
6. Estimate potential savings without automatically stopping or modifying production resources.

## Scope boundaries

### In scope

- AWS, Azure, and GCP cost/billing ingestion.
- Unified cost views and historical trends.
- Resource inventory needed to explain cost and identify optimization opportunities.
- Read-only optimization recommendations and estimated savings.
- Existing authentication and dashboard where practical.

### Deferred or excluded from the first project release

- Alibaba Cloud, Nebius, Databricks, and Kubernetes cost allocation.
- Jira, Slack, calendar/booking, power scheduling, and enterprise workflow integrations unless a retained feature has a hard dependency.
- Stripe/subscription billing.
- Production resource shutdown or other automatic infrastructure changes.
- Enterprise governance, chargeback, and broad FinOps workflow features.

Exclusions are feature-scope decisions. They must not be implemented by deleting upstream source modules indiscriminately.

## Confirmed source-code findings

### Billing importers

The repository contains provider-specific importers:

- `diworker/diworker/importers/aws.py` — `AWSReportImporter`, based on the shared CSV report importer. The inspected implementation includes AWS Cost and Usage Report field handling.
- `diworker/diworker/importers/azure.py` — `AzureImporterBase`, based on the shared report importer and supporting legacy and modern Azure consumption fields.
- `diworker/diworker/importers/gcp.py` — `GcpReportImporter`, based on the shared report importer. The inspected implementation processes cost, credits, SKU, service, resource, and location data.

These files establish billing-report processing support. They do not, by themselves, prove that each provider can be connected by a direct live billing API call. The upstream report/export acquisition flow still needs to be traced.

### Shared cloud adapter

The repository contains provider adapters:

- `tools/cloud_adapter/clouds/aws.py`
- `tools/cloud_adapter/clouds/azure.py`
- `tools/cloud_adapter/clouds/gcp.py`

The package dependency manifest is `tools/cloud_adapter/pyproject.toml`. It includes AWS SDK, Azure management/identity packages, and Google Cloud IAM, BigQuery, Compute, Storage, and Monitoring packages, alongside unrelated provider integrations.

### diworker dependencies

The `diworker/pyproject.toml` manifest specifies Python `>=3.12.11,<3.13`. It depends on `cloud-adapter`, ClickHouse, RabbitMQ/Kombu, MongoDB, pandas, PyArrow, OptScale clients, and shared packages. There is no `diworker/requirements.txt` at the inspected path; dependency management is via `pyproject.toml` and uv sources.

### Cloud pricing configuration

`optscale-deploy/overlay/user_template.yml` documents service credentials for AWS, Azure, Alibaba, and GCP. Its comments say these credentials are used for cloud pricing information and that recommendations will not work without them. GCP pricing configuration refers to BigQuery pricing export. These are pricing/recommendation credentials and must not be confused with each end-user's billing-account connection credentials.

### Deployment baseline

The existing Compose quickstart describes a near-full evaluation stack with 60+ services and recommends at least 8 CPU cores, 16 GB RAM, and 40 GB free disk. The unified Compose file consolidates first-party application images but still runs many independent services and supporting datastores. It is not, by itself, a reduced-resource deployment.

## Working principles

1. Preserve the upstream `origin/integration` history and all upstream licence/copyright notices.
2. Make project-specific changes only on `feature/reduced-cost-optimizer-scope`.
3. Preserve the current UI/UX unless a required integration change makes a targeted adjustment unavoidable.
4. Do not remove services based only on their names. Trace code imports, API routes, queues, schedulers, databases, and Compose `depends_on` edges first.
5. Do not commit real cloud credentials, private keys, generated `.env` files, or local secrets.
6. Keep the first release read-only: recommendations may estimate savings, but must not stop, resize, or delete live resources.
7. Validate Compose syntax, Python imports/tests, and the reduced service dependency graph before asking the user to run Docker locally.

## Implementation sequence

- [ ] Map account connection and credential storage for each provider.
- [ ] Trace report/export acquisition and importer scheduling for AWS, Azure, and GCP.
- [ ] Trace normalized expense/resource persistence and the API/UI paths that consume it.
- [ ] Map each Compose service to the retained user-facing features and transitive dependencies.
- [ ] Design a separate reduced Compose file; do not overwrite the upstream quickstart initially.
- [ ] Add safe sample configuration and setup documentation without real credentials.
- [ ] Validate the reduced deployment and document any remaining local-only tests.

## Current checkpoint

Repository: `RajeshShahapurkar/serverless-multicloud-cost-optimizer`

Working branch: `feature/reduced-cost-optimizer-scope`

Current phase: source and dependency discovery. No upstream service has been deleted and no Docker deployment has been started.
