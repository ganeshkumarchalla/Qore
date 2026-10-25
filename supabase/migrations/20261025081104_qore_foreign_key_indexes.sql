-- Cover owner-bound references so parent updates and account deletion do not
-- require full scans of a growing run/experiment ledger.
create index if not exists qore_runs_project_owner_idx
  on public.qore_runs (project_id, owner_id);
create index if not exists qore_experiments_project_owner_idx
  on public.qore_experiments (project_id, owner_id);
create index if not exists qore_experiments_simulation_owner_idx
  on public.qore_experiments (simulation_id, owner_id);
create index if not exists qore_experiments_optimization_owner_idx
  on public.qore_experiments (optimization_id, owner_id);
