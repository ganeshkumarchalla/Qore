-- Editable workspace files are separate from immutable quantum ledger records.
-- No demo files, credentials, or user data are seeded by this migration.
create schema if not exists qore_workspace_private;
revoke all on schema qore_workspace_private from public, anon, authenticated;
grant usage on schema qore_workspace_private to authenticated;

create or replace function qore_workspace_private.valid_path(value text)
returns boolean language sql immutable strict set search_path = '' as $$
  select char_length(value) between 1 and 512
    and value = normalize(value,NFC)
    and value = btrim(value)
    and position(chr(92) in value) = 0
    and value !~ '[[:cntrl:]:*?"<>|]'
    and not exists (select 1 from unnest(string_to_array(value, '/')) part
      where part in ('','.', '..') or char_length(part)>100 or part<>btrim(part));
$$;

create table if not exists public.qore_workspace_entries (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  path text not null check(qore_workspace_private.valid_path(path)),
  entry_type text not null check(entry_type in ('file','folder')),
  source text not null default '' check(octet_length(source)<=32768),
  kind text,
  version integer not null default 1 check(version>=1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  expires_at timestamptz,
  trash_batch_id uuid,
  check((entry_type='folder' and kind is null and source='')
    or (entry_type='file' and kind in ('python','qasm','json','markdown'))),
  check((deleted_at is null and expires_at is null and trash_batch_id is null)
    or (deleted_at is not null and expires_at=deleted_at+interval '48 hours' and trash_batch_id is not null))
);
create unique index if not exists qore_workspace_active_path
  on public.qore_workspace_entries(owner_id,path) where deleted_at is null;
create index if not exists qore_workspace_owner_updated
  on public.qore_workspace_entries(owner_id,updated_at);
create index if not exists qore_workspace_expiry
  on public.qore_workspace_entries(expires_at) where expires_at is not null;

create table if not exists public.qore_workspace_state (
  owner_id uuid primary key references auth.users(id) on delete cascade,
  active_file_id uuid,
  last_deleted_id uuid,
  updated_at timestamptz not null default now()
);
-- Retain only opaque removed IDs, never paths/source, to prevent stale offline
-- create requests from resurrecting a permanently removed file UUID.
create table if not exists qore_workspace_private.tombstones (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  removed_at timestamptz not null default now()
);
create index if not exists qore_workspace_tombstone_owner on qore_workspace_private.tombstones(owner_id);
alter table public.qore_workspace_entries enable row level security;
alter table public.qore_workspace_state enable row level security;
alter table qore_workspace_private.tombstones enable row level security;
revoke all on public.qore_workspace_entries, public.qore_workspace_state from public, anon, authenticated;
revoke all on qore_workspace_private.tombstones from public, anon, authenticated;
grant select on public.qore_workspace_entries, public.qore_workspace_state to authenticated;
create policy qore_workspace_read on public.qore_workspace_entries for select to authenticated
  using ((select auth.uid())=owner_id and (deleted_at is null or expires_at>statement_timestamp()));
create policy qore_workspace_state_read on public.qore_workspace_state for select to authenticated
  using ((select auth.uid())=owner_id);

create or replace function qore_workspace_private.entry_json(entry public.qore_workspace_entries)
returns jsonb language sql stable set search_path = '' as $$
  select jsonb_build_object('id',entry.id,'path',entry.path,'name',regexp_replace(entry.path,'^.*/',''),
    'type',entry.entry_type,'source',entry.source,'kind',entry.kind,'version',entry.version,
    'created_at',entry.created_at,'updated_at',entry.updated_at,'deleted_at',entry.deleted_at,'expires_at',entry.expires_at);
$$;

create or replace function qore_workspace_private.snapshot(owner uuid, at_time timestamptz)
returns jsonb language sql stable set search_path = '' as $$
  select jsonb_build_object(
    'files',coalesce((select jsonb_agg(qore_workspace_private.entry_json(e) order by e.path,e.id)
      from public.qore_workspace_entries e where e.owner_id=owner and e.deleted_at is null and e.entry_type='file'),'[]'::jsonb),
    'folders',coalesce((select jsonb_agg(qore_workspace_private.entry_json(e) order by e.path,e.id)
      from public.qore_workspace_entries e where e.owner_id=owner and e.deleted_at is null and e.entry_type='folder'),'[]'::jsonb),
    'trash',coalesce((select jsonb_agg(qore_workspace_private.entry_json(e) order by e.path,e.id)
      from public.qore_workspace_entries e where e.owner_id=owner and e.deleted_at is not null and e.expires_at>at_time),'[]'::jsonb),
    'active_file_id',(select s.active_file_id from public.qore_workspace_state s where s.owner_id=owner
      and exists(select 1 from public.qore_workspace_entries e where e.owner_id=owner and e.id=s.active_file_id and e.deleted_at is null and e.entry_type='file')),
    'last_deleted_id',(select s.last_deleted_id from public.qore_workspace_state s where s.owner_id=owner
      and exists(select 1 from public.qore_workspace_entries e where e.owner_id=owner and e.id=s.last_deleted_id and e.deleted_at is not null and e.expires_at>at_time)),
    'retention_hours',48,'server_time',at_time);
$$;

create or replace function qore_workspace_private.purge_owner(owner uuid, at_time timestamptz)
returns void language plpgsql set search_path = '' as $$
begin
  insert into qore_workspace_private.tombstones(id,owner_id,removed_at)
    select e.id,e.owner_id,at_time from public.qore_workspace_entries e
    where e.owner_id=owner and e.expires_at is not null and e.expires_at<=at_time on conflict(id) do nothing;
  delete from public.qore_workspace_entries e where e.owner_id=owner and e.expires_at is not null and e.expires_at<=at_time;
  update public.qore_workspace_state s set
    active_file_id=case when exists(select 1 from public.qore_workspace_entries e where e.owner_id=owner and e.id=s.active_file_id and e.entry_type='file' and e.deleted_at is null) then s.active_file_id else null end,
    last_deleted_id=case when exists(select 1 from public.qore_workspace_entries e where e.owner_id=owner and e.id=s.last_deleted_id and e.deleted_at is not null) then s.last_deleted_id else null end
    where s.owner_id=owner;
end;
$$;

create or replace function qore_workspace_private.bump_parents(owner uuid, paths text[], excluded uuid[], at_time timestamptz)
returns void language sql set search_path = '' as $$
  update public.qore_workspace_entries e set version=e.version+1,updated_at=at_time
    where e.owner_id=owner and e.deleted_at is null and e.entry_type='folder' and not(e.id=any(excluded))
      and exists(select 1 from unnest(paths) p where starts_with(p,e.path||'/'));
$$;

-- Only this private writer elevates table privileges. Authentication, ownership,
-- expiration and CAS rules are enforced here for every caller, including direct
-- REST clients. No owner_id or caller-controlled timestamps are accepted.
create or replace function qore_workspace_private.mutate(operation text, payload jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  owner uuid := auth.uid();
  at_time timestamptz;
  requested_id uuid;
  requested_type text;
  requested_path text;
  requested_source text;
  requested_kind text;
  expected integer;
  target public.qore_workspace_entries%rowtype;
  previous_found boolean;
  moving_ids uuid[];
  moving_paths text[];
  moving_types text[];
  collision boolean;
  invalid_parent boolean;
  temporary text;
  index integer;
begin
  if owner is null then return jsonb_build_object('error',jsonb_build_object('code','authentication_required')); end if;
  if operation is null or operation not in ('snapshot','put','delete','restore','state','undo')
    or jsonb_typeof(payload) is distinct from 'object' then
    return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_operation'));
  end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(owner::text,0));
  at_time := clock_timestamp();
  perform qore_workspace_private.purge_owner(owner,at_time);
  if operation='snapshot' then return qore_workspace_private.snapshot(owner,at_time); end if;

  if operation='state' then
    requested_id := (payload->>'active_file_id')::uuid;
    if requested_id is not null and not exists(select 1 from public.qore_workspace_entries e
      where e.owner_id=owner and e.id=requested_id and e.entry_type='file' and e.deleted_at is null) then
      return jsonb_build_object('error',jsonb_build_object('code','workspace_not_found'));
    end if;
    insert into public.qore_workspace_state(owner_id,active_file_id,updated_at) values(owner,requested_id,at_time)
      on conflict(owner_id) do update set active_file_id=excluded.active_file_id,updated_at=excluded.updated_at;
    return qore_workspace_private.snapshot(owner,at_time);
  end if;

  if operation='undo' then
    select s.last_deleted_id into requested_id from public.qore_workspace_state s where s.owner_id=owner;
    if requested_id is null then return qore_workspace_private.snapshot(owner,at_time); end if;
    select e.entry_type into requested_type from public.qore_workspace_entries e where e.owner_id=owner and e.id=requested_id;
    operation := 'restore';
  else
    requested_id := (payload->>'id')::uuid;
    requested_type := payload->>'type';
  end if;
  if requested_id is null or requested_type is null or requested_type not in ('file','folder') then
    return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_operation'));
  end if;
  select * into target from public.qore_workspace_entries e where e.owner_id=owner and e.id=requested_id for update;
  previous_found := found;
  if previous_found and target.entry_type<>requested_type then
    return jsonb_build_object('error',jsonb_build_object('code','workspace_not_found'));
  end if;

  if operation in ('put','delete') then
    if payload ? 'expected_version' then
      if jsonb_typeof(payload->'expected_version')<>'number' or (payload->>'expected_version')!~'^(0|[1-9][0-9]{0,8})$' then
        return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_version'));
      end if;
      expected := (payload->>'expected_version')::integer;
    else expected := 0;
    end if;
  end if;

  if operation='put' then
    requested_path := payload->>'path';
    requested_source := coalesce(payload->>'source','');
    requested_kind := payload->>'kind';
    if jsonb_typeof(payload->'path') is distinct from 'string' or requested_path is null or not qore_workspace_private.valid_path(requested_path) then
      return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_path'));
    end if;
    if requested_type='folder' then requested_source := ''; requested_kind := null;
    elsif requested_kind is null or requested_kind not in ('python','qasm','json','markdown') then
      return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_kind'));
    end if;
    if (payload ? 'source' and jsonb_typeof(payload->'source')<>'string' and requested_type='file') or octet_length(requested_source)>32768 then
      return jsonb_build_object('error',jsonb_build_object('code','workspace_source_too_large'));
    end if;
    if previous_found then
      if target.deleted_at is not null then return jsonb_build_object('error',jsonb_build_object('code','workspace_deleted')); end if;
      if target.path=requested_path and target.source=requested_source and target.kind is not distinct from requested_kind then
        return qore_workspace_private.entry_json(target);
      end if;
      if target.version<>expected then return jsonb_build_object('error',jsonb_build_object('code','workspace_version_conflict')); end if;
      if requested_type='folder' and starts_with(requested_path,target.path||'/') then
        return jsonb_build_object('error',jsonb_build_object('code','workspace_path_conflict'));
      end if;
    else
      if expected<>0 or exists(select 1 from public.qore_workspace_entries e where e.id=requested_id)
        or exists(select 1 from qore_workspace_private.tombstones t where t.id=requested_id and t.owner_id<>owner) then
        return jsonb_build_object('error',jsonb_build_object('code','workspace_not_found'));
      end if;
      if exists(select 1 from qore_workspace_private.tombstones t where t.id=requested_id and t.owner_id=owner) then
        return jsonb_build_object('error',jsonb_build_object('code','workspace_deleted'));
      end if;
      if (select count(*) from public.qore_workspace_entries e where e.owner_id=owner)>=1000 then
        return jsonb_build_object('error',jsonb_build_object('code','workspace_full'));
      end if;
    end if;
    if (select coalesce(sum(octet_length(e.source)),0) from public.qore_workspace_entries e where e.owner_id=owner)
      -coalesce(octet_length(target.source),0)+octet_length(requested_source)>16777216 then
      return jsonb_build_object('error',jsonb_build_object('code','workspace_full'));
    end if;
    if previous_found then
      select array_agg(e.id order by e.id),
        array_agg(requested_path||substring(e.path from char_length(target.path)+1) order by e.id),
        array_agg(e.entry_type order by e.id)
      into moving_ids,moving_paths,moving_types from public.qore_workspace_entries e
      where e.owner_id=owner and e.deleted_at is null and
        (e.id=requested_id or (requested_type='folder' and starts_with(e.path,target.path||'/')));
    else
      moving_ids := array[requested_id]; moving_paths := array[requested_path]; moving_types := array[requested_type];
    end if;
    if exists(select 1 from unnest(moving_paths) p where not qore_workspace_private.valid_path(p)) then
      return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_path'));
    end if;
    with final as (
      select e.id,e.path,e.entry_type from public.qore_workspace_entries e where e.owner_id=owner and e.deleted_at is null and not(e.id=any(moving_ids))
      union all select r.id,r.path,r.entry_type from unnest(moving_ids,moving_paths,moving_types) r(id,path,entry_type)
    ) select exists(select 1 from final group by path having count(*)>1),
      exists(select 1 from final f join final child on child.id<>f.id and starts_with(child.path,f.path||'/') where f.entry_type='file')
      into collision,invalid_parent;
    if collision or invalid_parent then return jsonb_build_object('error',jsonb_build_object('code','workspace_path_conflict')); end if;
    if previous_found then
      temporary := '__qore_move_'||replace(gen_random_uuid()::text,'-','')||'/';
      update public.qore_workspace_entries e set path=temporary||e.id::text where e.owner_id=owner and e.id=any(moving_ids);
      for index in 1..array_length(moving_ids,1) loop
        update public.qore_workspace_entries e set path=moving_paths[index],version=e.version+1,updated_at=at_time
          where e.owner_id=owner and e.id=moving_ids[index];
      end loop;
      update public.qore_workspace_entries e set source=requested_source,kind=requested_kind where e.owner_id=owner and e.id=requested_id;
    else
      insert into public.qore_workspace_entries(id,owner_id,path,entry_type,source,kind,created_at,updated_at)
        values(requested_id,owner,requested_path,requested_type,requested_source,requested_kind,at_time,at_time);
    end if;
    perform qore_workspace_private.bump_parents(owner,array[requested_path,target.path],moving_ids,at_time);
    select * into target from public.qore_workspace_entries e where e.owner_id=owner and e.id=requested_id;
    return qore_workspace_private.entry_json(target);
  end if;

  if not previous_found then return jsonb_build_object('error',jsonb_build_object('code','workspace_not_found')); end if;
  if operation='delete' then
    if target.deleted_at is not null then return qore_workspace_private.snapshot(owner,at_time); end if;
    if expected<1 or target.version<>expected then
      return jsonb_build_object('error',jsonb_build_object('code','workspace_version_conflict'));
    end if;
    select array_agg(e.id) into moving_ids from public.qore_workspace_entries e where e.owner_id=owner and e.deleted_at is null
      and (e.id=requested_id or (requested_type='folder' and starts_with(e.path,target.path||'/')));
    update public.qore_workspace_entries e set deleted_at=at_time,expires_at=at_time+interval '48 hours',trash_batch_id=requested_id,
      version=e.version+1,updated_at=at_time where e.owner_id=owner and e.id=any(moving_ids);
    insert into public.qore_workspace_state(owner_id,last_deleted_id,updated_at) values(owner,requested_id,at_time)
      on conflict(owner_id) do update set last_deleted_id=excluded.last_deleted_id,updated_at=excluded.updated_at;
    perform qore_workspace_private.bump_parents(owner,array[target.path],moving_ids,at_time);
    perform qore_workspace_private.purge_owner(owner,at_time);
    return qore_workspace_private.snapshot(owner,at_time);
  end if;

  if operation='restore' then
    if target.deleted_at is null then return qore_workspace_private.snapshot(owner,at_time); end if;
    select array_agg(e.id) into moving_ids from public.qore_workspace_entries e where e.owner_id=owner and e.deleted_at is not null
      and e.expires_at>at_time and (e.id=requested_id or (requested_type='folder' and e.trash_batch_id=requested_id));
    with final as (
      select e.id,e.path,e.entry_type from public.qore_workspace_entries e where e.owner_id=owner and (e.deleted_at is null or e.id=any(moving_ids))
    ) select exists(select 1 from final group by path having count(*)>1),
      exists(select 1 from final f join final child on child.id<>f.id and starts_with(child.path,f.path||'/') where f.entry_type='file')
      into collision,invalid_parent;
    if collision or invalid_parent then return jsonb_build_object('error',jsonb_build_object('code','workspace_path_conflict')); end if;
    update public.qore_workspace_entries e set deleted_at=null,expires_at=null,trash_batch_id=null,version=e.version+1,updated_at=at_time
      where e.owner_id=owner and e.id=any(moving_ids);
    update public.qore_workspace_state s set last_deleted_id=case when s.last_deleted_id=requested_id then null else s.last_deleted_id end,updated_at=at_time where s.owner_id=owner;
    perform qore_workspace_private.bump_parents(owner,array[target.path],moving_ids,at_time);
    return qore_workspace_private.snapshot(owner,at_time);
  end if;
  return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_operation'));
exception
  when unique_violation then return jsonb_build_object('error',jsonb_build_object('code','workspace_path_conflict'));
  when invalid_text_representation or numeric_value_out_of_range then
    return jsonb_build_object('error',jsonb_build_object('code','invalid_workspace_operation'));
end;
$$;

-- The exposed function does not itself elevate privileges.
create or replace function public.qore_workspace(operation text, payload jsonb default '{}'::jsonb)
returns jsonb language sql security invoker set search_path = '' as $$
  select qore_workspace_private.mutate(operation,payload);
$$;

create or replace function qore_workspace_private.purge_expired()
returns integer language plpgsql security invoker set search_path = '' as $$
declare at_time timestamptz; removed integer:=0; cleanup_owner uuid;
begin
  for cleanup_owner in select distinct e.owner_id from public.qore_workspace_entries e
    where e.expires_at is not null and e.expires_at<=clock_timestamp() order by e.owner_id loop
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(cleanup_owner::text,0));
    at_time:=clock_timestamp();
    removed:=removed+(select count(*)::integer from public.qore_workspace_entries e
      where e.owner_id=cleanup_owner and e.expires_at is not null and e.expires_at<=at_time);
    perform qore_workspace_private.purge_owner(cleanup_owner,at_time);
  end loop;
  return removed;
end;
$$;

revoke execute on all functions in schema qore_workspace_private from public, anon, authenticated;
grant execute on function qore_workspace_private.mutate(text,jsonb) to authenticated;
revoke execute on function public.qore_workspace(text,jsonb) from public, anon, authenticated;
grant execute on function public.qore_workspace(text,jsonb) to authenticated;

create extension if not exists pg_cron with schema pg_catalog;
grant usage on schema cron to postgres;
grant all privileges on all tables in schema cron to postgres;
select cron.schedule('qore-workspace-expired-trash','*/5 * * * *',
  'select qore_workspace_private.purge_expired();');
