import os
import sqlite3
import subprocess


def test_upgrade_head_on_empty_database(tmp_path) -> None:
    database_path = tmp_path / "migration.db"
    env = os.environ | {
        "AAC_DATABASE_URL": f"sqlite+aiosqlite:///{database_path}",
        "AAC_AUTH_SECRET": "migration-test-auth-secret",
        "AAC_ADMIN_API_KEY": "migration-test-admin-key",
        "AAC_PARTNER_API_KEY": "migration-test-partner-key",
    }

    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database_path) as connection:
        current_revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert current_revision == ("20260821_0010",)
    assert {"users", "knowledge_documents", "knowledge_chunks", "knowledge_indexes"} <= tables
