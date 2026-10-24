-- QORE cloud ledger (optional Supabase persistence)
-- Apply only after linking a Supabase project. The local SQLite ledger remains the default.

create table if not exists public.qore_projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 120),
  source text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.qore_runs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid references public.qore_projects(id) on delete set null,
  kind text not null check (kind in ('simulation', 'optimization')),
  source text not null,
  source_hash text not null,
  configuration jsonb not null default '{}'::jsonb,
  result jsonb,
  error jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.qore_experiments (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid references public.qore_projects(id) on delete set null,
  simulation_id uuid references public.qore_runs(id) on delete set null,
  optimization_id uuid references public.qore_runs(id) on delete set null,
  name text not null check (char_length(name) between 1 and 120),
  source text not null,
  source_hash text not null,
  snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists qore_projects_owner_updated_idx on public.qore_projects(owner_id, updated_at desc);
create index if not exists qore_runs_owner_created_idx on public.qore_runs(owner_id, created_at desc);
create index if not exists qore_experiments_owner_created_idx on public.qore_experiments(owner_id, created_at desc);

alter table public.qore_projects enable row level security;
alter table public.qore_runs enable row level security;
alter table public.qore_experiments enable row level security;

create policy "owners manage qore projects" on public.qore_projects
  for all to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);

create policy "owners manage qore runs" on public.qore_runs
  for all to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);

create policy "owners manage qore experiments" on public.qore_experiments
  for all to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);
