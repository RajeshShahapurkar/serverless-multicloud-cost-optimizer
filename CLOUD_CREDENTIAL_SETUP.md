# Cloud Account Credential and Billing Setup Notes

Branch: `feature/reduced-cost-optimizer-scope`

This file records the provider credential fields declared by the current cloud adapters. It is an implementation reference, not a request to paste credentials into ChatGPT or GitHub.

## AWS (`aws_cnr`)

Adapter: `tools/cloud_adapter/clouds/aws.py`

Required base fields:
- `access_key_id`
- `secret_access_key` (protected)

Optional fields include:
- `bucket_name`
- `bucket_prefix`
- `report_name`
- `region_name`
- `config_scheme`
- `linked`
- `assume_role_account_id`
- `assume_role_name`
- `assume_role_session_name`
- `assume_role_external_id`
- `included_regions` / `excluded_regions`
- `cur_version`
- `use_edp_discount`

The AWS adapter supports report configuration schemes: find an existing report, create a report, or use a bucket-only configuration. Its report reader searches the configured S3 bucket/prefix/report name for CUR CSV or Parquet files. The adapter's `configure_report()` skips report setup for linked accounts; otherwise it selects the configured scheme and applies it.

The account controller has an additional assumed-role flow: when role account/name are used, it sources the AWS access key/secret from platform-level `/service_credentials/aws/` and does not allow static access-key fields in the same request. Treat the role's trust relationship and external ID as security-sensitive.

## Azure (`azure_cnr`)

Adapter: `tools/cloud_adapter/clouds/azure.py`

Required base fields:
- `subscription_id`
- `secret` (protected)
- `client_id`
- `tenant`

Optional fields include:
- `expense_import_scheme`
- `base_url`
- CSP partner fields: `partner_tenant`, `partner_client_id`, `partner_secret`
- Export fields: `export_name`, `sa_connection_string` (protected), `container`, `directory`

The adapter checks the subscription and decides an expense-import scheme. Based on account support/configuration, the scheme may be Consumption API usage, raw usage, partner raw usage, or Azure export. Export mode validates access to the configured storage export. The importer factory maps `azure_cnr` plus `export` to `AzureExportImporter`; other supported Azure schemes map to `AzureApiImporter`.

For the MVP, prefer the native Consumption API path where the subscription supports it. Keep export mode documented as an alternative for unsupported subscription types, not as a requirement for every user.

## GCP (`gcp_cnr`)

Adapter: `tools/cloud_adapter/clouds/gcp.py`

Required fields:
- `billing_data` object containing `dataset_name` and `table_name`
- `credentials` service-account JSON object (protected)

Optional:
- top-level `project_id`
- `billing_data.project_id`
- `pricing_data` object containing `dataset_name` and `table_name`, with optional project ID

Important correction to the earlier high-level audit: although `GcpReportImporter` is registered in the importer factory, it inherits `BaseReportImporter` rather than `CSVBaseReportImporter`. Its `load_raw_data()` calls `self.cloud_adapter.get_usage(current_day, end_date)`. The GCP adapter's `get_usage()` queries the configured BigQuery billing export table. Therefore the current GCP path is API/query-based against a BigQuery billing export, not a report-file importer.

The GCP adapter also validates project/billing configuration, cloud connection and BigQuery access. The service account must have the necessary access to the billing export dataset/table and any resource/pricing APIs needed by retained features. The checked-in service-credential template separately describes platform pricing credentials; those are distinct from a customer's billing-data credentials.

## Security rules

- Never commit real AWS keys, Azure client secrets, storage connection strings, GCP service-account JSON, or private keys.
- Never paste secrets into chat.
- Use least-privilege roles/permissions and a dedicated test account/project/subscription.
- Keep sample values clearly fake and local secrets in ignored environment/config files.
- Confirm the current UI/API stores protected credential fields using the platform's existing encryption mechanisms; do not introduce a new plaintext storage path.

## Live integration verification still required

The adapter declarations and controller flow establish what fields the source expects. They do not prove the cloud-side IAM policy is configured correctly or that the account can return complete billing data. Each provider needs a controlled end-to-end test using a non-production account and a small date range.
