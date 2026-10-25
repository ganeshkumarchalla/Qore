-- Private, durable QORE workspaces. No seeded circuits or demo records.
create table if not exists public.qore_projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 100),
  source text not null check (octet_length(source) <= 32768),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists qore_projects_identity_owner on public.qore_projects(id, owner_id);
create table if not exists public.qore_runs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid,
  kind text not null check (kind in ('simulation','optimization')),
  source text not null check (octet_length(source) <= 32768),
  source_hash text not null,
  configuration jsonb not null default '{}'::jsonb,
  result jsonb not null,
  error jsonb,
  created_at timestamptz not null default now()
);
create unique index if not exists qore_runs_identity_owner on public.qore_runs(id, owner_id);
create table if not exists public.qore_experiments (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid,
  simulation_id uuid,
  optimization_id uuid,
  name text not null check (char_length(name) between 1 and 100),
  source text not null check (octet_length(source) <= 32768),
  source_hash text not null,
  snapshot jsonb not null,
  created_at timestamptz not null default now()
);
do $$ begin
  if not exists (select 1 from pg_constraint where conname='qore_runs_project_owner' and conrelid='public.qore_runs'::regclass) then
    alter table public.qore_runs add constraint qore_runs_project_owner foreign key (project_id, owner_id) references public.qore_projects(id, owner_id);
  end if;
  if not exists (select 1 from pg_constraint where conname='qore_experiments_project_owner' and conrelid='public.qore_experiments'::regclass) then
    alter table public.qore_experiments add constraint qore_experiments_project_owner foreign key (project_id, owner_id) references public.qore_projects(id, owner_id);
    alter table public.qore_experiments add constraint qore_experiments_simulation_owner foreign key (simulation_id, owner_id) references public.qore_runs(id, owner_id);
    alter table public.qore_experiments add constraint qore_experiments_optimization_owner foreign key (optimization_id, owner_id) references public.qore_runs(id, owner_id);
  end if;
end $$;
create index if not exists qore_projects_owner_updated_idx on public.qore_projects(owner_id, updated_at desc);
create index if not exists qore_runs_owner_created_idx on public.qore_runs(owner_id, created_at desc);
create index if not exists qore_experiments_owner_created_idx on public.qore_experiments(owner_id, created_at desc);
alter table public.qore_projects enable row level security;
alter table public.qore_runs enable row level security;
alter table public.qore_experiments enable row level security;
revoke all on public.qore_projects, public.qore_runs, public.qore_experiments from anon;
revoke all on public.qore_runs, public.qore_experiments from authenticated;
grant select, insert, update, delete on public.qore_projects to authenticated;
grant select, insert on public.qore_runs, public.qore_experiments to authenticated;
drop policy if exists "owners manage qore projects" on public.qore_projects;
drop policy if exists "owners manage qore runs" on public.qore_runs;
drop policy if exists "owners manage qore experiments" on public.qore_experiments;
drop policy if exists qore_project_owner on public.qore_projects;
drop policy if exists qore_run_read on public.qore_runs;
drop policy if exists qore_run_create on public.qore_runs;
drop policy if exists qore_experiment_read on public.qore_experiments;
drop policy if exists qore_experiment_create on public.qore_experiments;
create policy qore_project_owner on public.qore_projects for all to authenticated
  using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);
create policy qore_run_read on public.qore_runs for select to authenticated using ((select auth.uid()) = owner_id);
create policy qore_run_create on public.qore_runs for insert to authenticated with check ((select auth.uid()) = owner_id);
create policy qore_experiment_read on public.qore_experiments for select to authenticated using ((select auth.uid()) = owner_id);
create policy qore_experiment_create on public.qore_experiments for insert to authenticated with check ((select auth.uid()) = owner_id);
