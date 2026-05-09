from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_post_create_like_follow_publishes_events(app_client, auth_headers) -> None:
    alice = uuid.uuid4()
    bob = uuid.uuid4()

    # bob follows alice
    r = await app_client.post(
        "/follow", json={"followee_id": str(alice)}, headers=auth_headers(bob)
    )
    assert r.status_code == 204

    # cannot follow self
    r = await app_client.post(
        "/follow", json={"followee_id": str(bob)}, headers=auth_headers(bob)
    )
    assert r.status_code == 400

    # alice creates a post
    r = await app_client.post(
        "/posts",
        json={"content": "hello world", "media_keys": ["users/alice/abc.jpg"]},
        headers=auth_headers(alice),
    )
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["content"] == "hello world"
    assert post["media_urls"][0].startswith("https://s3.fake/")
    post_id = post["id"]

    # bob likes the post (idempotent: second call publishes nothing)
    r = await app_client.post(f"/posts/{post_id}/like", headers=auth_headers(bob))
    assert r.status_code == 204
    r = await app_client.post(f"/posts/{post_id}/like", headers=auth_headers(bob))
    assert r.status_code == 204

    # list alice's posts
    r = await app_client.get(f"/posts/{alice}", headers=auth_headers(bob))
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == post_id

    # bob unfollows alice
    r = await app_client.request(
        "DELETE", "/follow", json={"followee_id": str(alice)}, headers=auth_headers(bob)
    )
    assert r.status_code == 204

    # collected SNS events: follow.created, post.created, post.liked, follow.deleted
    events = app_client._transport.app.state.fake_sns.events  # type: ignore[attr-defined]
    types = [e["event_type"] for e in events]
    assert "follow.created" in types
    assert "post.created" in types
    assert "post.liked" in types
    assert "follow.deleted" in types
    # idempotent like: only one post.liked
    assert types.count("post.liked") == 1

    # envelope shape
    pc = next(e for e in events if e["event_type"] == "post.created")
    assert pc["data"]["post_id"] == post_id
    assert pc["data"]["author_id"] == str(alice)
    assert pc["actor_id"] == str(alice)
    assert "event_id" in pc and "occurred_at" in pc


@pytest.mark.asyncio
async def test_unauthenticated_rejected(app_client) -> None:
    r = await app_client.post("/posts", json={"content": "x"})
    assert r.status_code in (401, 403)

    r = await app_client.get(f"/posts/{uuid.uuid4()}")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_presign_returns_url(app_client, auth_headers) -> None:
    alice = uuid.uuid4()
    r = await app_client.post(
        "/media/presign",
        json={"content_type": "image/jpeg", "size_bytes": 1024},
        headers=auth_headers(alice),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["upload_url"].startswith("https://s3.fake/")
    assert body["media_key"].startswith(f"users/{alice}/")
    assert body["media_key"].endswith(".jpg")
