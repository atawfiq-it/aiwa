"""add_characters_and_image_mode

Revision ID: 79bca1ddbb39
Revises: ff16f8d1a06b
Create Date: 2026-11-05 14:58:09.207520

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "79bca1ddbb39"
down_revision: str | None = "ff16f8d1a06b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Create characters table if it does not already exist
    if "characters" not in existing_tables:
        op.create_table(
            "characters",
            sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "avatar_emoji",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="🤖",
            ),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("system_prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "voice_persona",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="af_heart",
            ),
            sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_characters"),
        )
        op.create_index(op.f("ix_characters_name"), "characters", ["name"], unique=False)

    # 2. Add columns to conversations if not already present
    existing_columns = [col["name"] for col in inspector.get_columns("conversations")]
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        if "character_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("character_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_conversations_character_id", "characters", ["character_id"], ["id"]
            )
        if "image_gen_mode" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "image_gen_mode",
                    sqlmodel.sql.sqltypes.AutoString(),
                    nullable=False,
                    server_default="none",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("conversations")]

    with op.batch_alter_table("conversations", schema=None) as batch_op:
        if "character_id" in existing_columns:
            batch_op.drop_constraint("fk_conversations_character_id", type_="foreignkey")
            batch_op.drop_column("character_id")
        if "image_gen_mode" in existing_columns:
            batch_op.drop_column("image_gen_mode")

    existing_tables = inspector.get_table_names()
    if "characters" in existing_tables:
        op.drop_index(op.f("ix_characters_name"), table_name="characters")
        op.drop_table("characters")
