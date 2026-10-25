// Explicit in-memory API fixture for browser contract checks, never a live database.
function workspaceFixture() {
  let entries = [], active = null, last = null, offset = 0;
  const fixture = { failWrites: false, requests: [], get entries() { return entries; },
    advance(milliseconds) { offset += milliseconds; },
    get active() { return active; },
    editRemotely(id, source) { const file = entries.find(entry => entry.id === id); file.source = source; file.version++; },
  };
  const now = () => Date.now() + offset;
  const snapshot = () => {
    entries = entries.filter(entry => !entry.expires_at || Date.parse(entry.expires_at) > now());
    if (!entries.some(entry => entry.id === last && entry.deleted_at)) last = null;
    return { files: entries.filter(entry => entry.type === 'file' && !entry.deleted_at),
      folders: entries.filter(entry => entry.type === 'folder' && !entry.deleted_at), trash: entries.filter(entry => entry.deleted_at),
      active_file_id: active, last_deleted_id: last, retention_hours: 48, server_time: new Date(now()).toISOString() };
  };
  fixture.handle = async route => {
    const req = route.request(), pathname = new URL(req.url()).pathname;
    if (!pathname.startsWith('/api/workspace')) return false;
    const method = req.method(), tail = pathname.slice('/api/workspace'.length), body = req.postDataJSON();
    fixture.requests.push({ method, path: tail });
    const reply = (status, result) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(result) });
    snapshot();
    if (fixture.failWrites && method !== 'GET') { await reply(503, { error: { message: 'Mock offline: draft was not saved to the server.' } }); return true; }
    if (method === 'GET') {
      await reply(200, tail === '/trash' ? { trash: snapshot().trash, retention_hours: 48, server_time: new Date(now()).toISOString() } : snapshot()); return true;
    }
    if (tail === '/state') { active = body.active_file_id; await reply(200, snapshot()); return true; }
    const match = tail.match(/^\/(files|folders)\/([^/]+)(\/restore)?$/);
    const id = tail === '/undo' ? last : match?.[2];
    const type = match?.[1] === 'folders' ? 'folder' : 'file';
    const existing = entries.find(entry => entry.id === id);
    if (method === 'PUT' && match) {
      if (existing?.deleted_at || (existing ? existing.version !== body.expected_version : body.expected_version !== 0)
        || entries.some(entry => !entry.deleted_at && entry.id !== id && entry.path === body.path)) {
        if (existing && !existing.deleted_at && existing.path === body.path && existing.source === (body.source ?? '')) { await reply(200, existing); return true; }
        await reply(409, { error: { message: 'Version or path conflict' } }); return true;
      }
      const entry = { id, path: body.path, name: body.path.split('/').pop(), type, source: body.source ?? '', kind: type === 'file' ? body.kind : null,
        version: (existing?.version ?? 0) + 1, created_at: existing?.created_at ?? new Date(now()).toISOString(),
        updated_at: new Date(now()).toISOString(), deleted_at: null, expires_at: null };
      if (existing && type === 'folder' && existing.path !== body.path) entries.forEach(item => {
        if (!item.deleted_at && item.path.startsWith(existing.path + '/')) { item.path = body.path + item.path.slice(existing.path.length); item.version++; }
      });
      entries = [...entries.filter(item => item.id !== id), entry]; await reply(200, entry); return true;
    }
    if (method === 'DELETE' && existing) {
      if (!existing.deleted_at && existing.version !== body.expected_version) { await reply(409, { error: { message: 'Version conflict' } }); return true; }
      if (!existing.deleted_at) {
        const stamp = new Date(now()).toISOString(), expiry = new Date(now() + 48 * 3600000).toISOString();
        entries.forEach(item => { if (item.id === id || (type === 'folder' && item.path.startsWith(existing.path + '/'))) {
          item.deleted_at = stamp; item.expires_at = expiry; item.version++; item.batch = id; if (active === item.id) active = null;
        } });
        last = id;
      }
      await reply(200, snapshot()); return true;
    }
    if (method === 'POST' && existing) {
      const batch = entries.filter(item => item.id === id || (existing.type === 'folder' && item.batch === id));
      if (batch.some(item => entries.some(other => other.id !== item.id && !other.deleted_at && other.path === item.path))) {
        await reply(409, { error: { message: 'Restore path occupied' } }); return true;
      }
      batch.forEach(item => { item.deleted_at = null; item.expires_at = null; item.version++; });
      if (last === id) last = null; await reply(200, snapshot()); return true;
    }
    await reply(404, { error: { message: 'Recovery period expired or entry not found' } }); return true;
  };
  return fixture;
}
module.exports = { workspaceFixture };
