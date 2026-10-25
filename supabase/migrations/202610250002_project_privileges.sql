-- Supabase default grants can include TRUNCATE, which is outside row security.
-- Explicitly reduce authenticated project privileges to the app's CRUD surface.
revoke all on public.qore_projects from authenticated;
grant select, insert, update, delete on public.qore_projects to authenticated;
