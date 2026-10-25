-- Opaque tombstones are accessible only to the controlled database writer.
-- Make the intentional deny explicit so advisors do not treat missing policy
-- as an accidental omission. No client table grants are introduced.
create policy qore_workspace_tombstones_deny on qore_workspace_private.tombstones
  for all to authenticated using (false) with check (false);
