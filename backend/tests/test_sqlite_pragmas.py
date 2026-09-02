from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient


def test_sqlite_file_uses_wal(client: TestClient, test_db_path: Path) -> None:
    """journal_mode=WAL is file-level; the connect listener in db.py sets it."""
    assert test_db_path.exists()
    conn = sqlite3.connect(test_db_path)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()
    assert str(mode).lower() == "wal"
