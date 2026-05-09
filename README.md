# post-service

Posts, likes, follows. Issues S3 pre-signed URLs for media. Publishes events to SNS topic `post-events`.

## Endpoints
- `POST /posts` — create a post (JWT)
- `GET /posts/by-id/{post_id}` — single post (JWT)
- `GET /posts/{user_id}` — paginated user timeline (JWT)
- `POST /posts/{post_id}/like` / `DELETE /posts/{post_id}/like` (JWT)
- `POST /follow` `{followee_id}` / `DELETE /follow` `{followee_id}` (JWT)
- `GET /follows/{user_id}/followers` / `GET /follows/{user_id}/following` (JWT)
- `POST /media/presign` — `{content_type, size_bytes}` → pre-signed PUT URL (JWT)
- `GET /health/live` / `GET /health/ready`

## Local dev

```bash
cp .env.example .env
docker-compose up --build
docker-compose exec api alembic upgrade head
```

`docker-compose` brings up Postgres + LocalStack (SNS + S3) + the API.

## Tests

```bash
poetry install
poetry run pytest
```
