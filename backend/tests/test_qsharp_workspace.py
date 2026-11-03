import sqlite3

import pytest

from qore.workspace import initialize_workspace, FileInput


def test_qsharp_file_input():
    assert FileInput(path="main.qs", source="", kind="qsharp", expected_version=0).kind == "qsharp"


def test_qsharp_schema_upgrade_preserves_existing_records():
    db = sqlite3.connect(":memory:")
    initialize_workspace(db)
    schema = db.execute("SELECT sql FROM sqlite_master WHERE name='workspace_entries'").fetchone()[0]
    db.execute("DROP TABLE workspace_entries")
    db.execute(schema.replace("'qsharp',", ""))
    rows = [
        ("active", "owner", "main.py", "file", "original", "python", 3, "created", "updated", None, None, None),
        ("trash", "owner", "old.qasm", "file", "deleted source", "qasm", 4, "created", "updated", "deleted", "expiry", "batch"),
    ]
    db.executemany("INSERT INTO workspace_entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    db.execute("INSERT INTO workspace_state VALUES ('owner','active','trash','updated')")
    db.commit()
    initialize_workspace(db)
    initialize_workspace(db)  # Startup remains idempotent.
    assert db.execute("SELECT * FROM workspace_entries ORDER BY id").fetchall() == rows
    assert db.execute("SELECT * FROM workspace_state").fetchone() == ("owner", "active", "trash", "updated")
    db.execute("INSERT INTO workspace_entries VALUES ('qs','owner','main.qs','file','','qsharp',1,'c','u',NULL,NULL,NULL)")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO workspace_entries VALUES ('duplicate','owner','main.qs','file','','qsharp',1,'c','u',NULL,NULL,NULL)")
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
