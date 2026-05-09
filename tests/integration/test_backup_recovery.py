"""Backup / recovery test (post-service)."""
from __future__ import annotations

import shutil
import subprocess
import uuid

import pytest

_PG_TOOLS_AVAILABLE = (
    shutil.which("pg_dump") is not None and shutil.which("pg_restore") is not None
)


def _libpq_url(asyncpg_url: str) -> str:
    return asyncpg_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.mark.skipif(not _PG_TOOLS_AVAILABLE, reason="pg_dump / pg_restore not installed")
@pytest.mark.asyncio
async def test_pg_dump_then_restore_round_trip(
    app_client, auth_headers, postgres_url, tmp_path
):
    alice = uuid.uuid4()
    content = f"recover-{uuid.uuid4()}"

    # 1. Seed a post via the API.
    r = await app_client.post(
        "/posts", json={"content": content, "media_keys": []},
        headers=auth_headers(alice),
    )
    assert r.status_code == 201, r.text
    post_id = r.json()["id"]

    # 2. Dump.
    libpq = _libpq_url(postgres_url)
    dump = tmp_path / "backup.dump"
    subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--dbname", libpq,
         "--file", str(dump)],
        check=True,
    )
    assert dump.exists() and dump.stat().st_size > 0

    # 3. Drop schema.
    from post_service import db as db_mod  # noqa: PLC0415
    async with db_mod.engine.begin() as conn:
        await conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")
        await conn.exec_driver_sql('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # 4. Restore.
    subprocess.run(
        ["pg_restore", "--no-owner", "--dbname", libpq, str(dump)],
        check=True,
    )

    # 5. Verify the row is back via GET /posts/by-id/{id}.
    r = await app_client.get(f"/posts/by-id/{post_id}", headers=auth_headers(alice))
    assert r.status_code == 200, r.text
    assert r.json()["content"] == content
