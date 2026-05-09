"""create posts, likes, follows tables

Revision ID: 0001
Revises:
Create Date: 2026-05-09

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("media_keys", postgresql.ARRAY(sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::text[]")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_posts_author_created", "posts", ["author_id", sa.text("created_at DESC")])

    op.create_table(
        "likes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "post_id"),
    )
    op.create_index("idx_likes_post", "likes", ["post_id"])

    op.create_table(
        "follows",
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("follower_id", "followee_id"),
        sa.CheckConstraint("follower_id <> followee_id", name="ck_follows_no_self"),
    )
    op.create_index("idx_follows_followee", "follows", ["followee_id"])
    op.create_index("idx_follows_follower", "follows", ["follower_id"])


def downgrade() -> None:
    op.drop_index("idx_follows_follower", table_name="follows")
    op.drop_index("idx_follows_followee", table_name="follows")
    op.drop_table("follows")
    op.drop_index("idx_likes_post", table_name="likes")
    op.drop_table("likes")
    op.drop_index("idx_posts_author_created", table_name="posts")
    op.drop_table("posts")
