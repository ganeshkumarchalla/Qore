# Workspace API and recovery model

Workspace entries have a stable UUID, relative path, type, optional source kind, version, timestamps, and deletion metadata. File source may be empty. Folder operations cover the active subtree atomically. Expected versions prevent stale tabs from silently overwriting newer server state.

Deleting creates a Trash batch and sets an exact expiry 48 hours later. Undo restores the latest eligible batch. Direct restore checks every destination first; a conflict aborts the whole operation. Expired content is unavailable even before physical cleanup. Tombstones prevent stale clients from recreating a deleted identity.

Paths use slash-separated safe segments. Empty, dot, parent, backslash, control, and reserved characters are rejected. A workspace path is a logical QORE name and never grants host filesystem access.

The server allows 1,000 active-plus-Trash entries and 16 MiB of aggregate retained source per browser workspace. These server constraints are distinct from browser storage quotas. Export important source before clearing site data or migrating origins.
