-- Core schema for the Serverless Multi-Cloud Cost Optimizer.
-- OAuth/client secrets are never stored in these public tables.

create table if not exists public.cloud_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  provider text not null check (provider in ('aws','gcp','azure')),
  display_name text not null,
  status text not null default 'pending'
    check (status in ('pending','connected','error','disconnected')),
  auth_method text not null default 'oauth',
  account_identifier text,
  region text,
  token_expires_at timestamptz,
  last_synced_at timestamptz,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, provider)
);

create table if not exists public.cloud_resources (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  cloud_account_id uuid not null references public.cloud_accounts(id) on delete cascade,
  provider text not null,
  resource_id text not null,
  resource_type text not null,
  resource_name text,
  region text,
  status text,
  metadata jsonb not null default '{}'::jsonb,
  collected_at timestamptz not null default now(),
  unique (cloud_account_id, resource_id)
);

create table if not exists public.usage_metrics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  cloud_resource_id uuid not null references public.cloud_resources(id) on delete cascade,
  metric_name text not null,
  metric_value numeric,
  unit text,
  recorded_at timestamptz not null default now()
);

create table if not exists public.cost_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  cloud_account_id uuid not null references public.cloud_accounts(id) on delete cascade,
  provider text not null,
  amount numeric not null default 0,
  currency text not null default 'USD',
  service_name text,
  period_start date,
  period_end date,
  metadata jsonb not null default '{}'::jsonb,
  collected_at timestamptz not null default now()
);
