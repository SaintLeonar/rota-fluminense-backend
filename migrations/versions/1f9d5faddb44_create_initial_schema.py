"""Create the initial application schema.

Revision ID: 1f9d5faddb44
Revises:
Create Date: 2026-09-11 03:42:32.078413

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1f9d5faddb44"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tourist location and evaluation tables."""
    op.create_table(
        "locais_turisticos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("categoria", sa.String(length=80), nullable=False),
        sa.Column("descricao", sa.String(length=2000), nullable=False),
        sa.Column("cidade", sa.String(length=120), nullable=False),
        sa.Column("bairro", sa.String(length=120), nullable=False),
        sa.Column("regiao", sa.String(length=80), nullable=False),
        sa.Column("imagem", sa.String(length=500), nullable=False),
        sa.Column(
            "destaque",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "latitude",
            sa.Numeric(precision=8, scale=6),
            nullable=False,
        ),
        sa.Column(
            "longitude",
            sa.Numeric(precision=9, scale=6),
            nullable=False,
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90",
            name="ck_locais_turisticos_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name="ck_locais_turisticos_longitude_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_locais_turisticos_categoria",
        "locais_turisticos",
        ["categoria"],
        unique=False,
    )
    op.create_index(
        "ix_locais_turisticos_cidade",
        "locais_turisticos",
        ["cidade"],
        unique=False,
    )
    op.create_index(
        "ix_locais_turisticos_slug",
        "locais_turisticos",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "avaliacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("autor", sa.String(length=120), nullable=False),
        sa.Column("nota", sa.Integer(), nullable=False),
        sa.Column("comentario", sa.String(length=1000), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "comentario IS NULL OR length(trim(comentario)) > 0",
            name="ck_avaliacoes_comentario_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(autor)) > 0",
            name="ck_avaliacoes_autor_not_blank",
        ),
        sa.CheckConstraint(
            "local_id > 0",
            name="ck_avaliacoes_local_id_positive",
        ),
        sa.CheckConstraint(
            "nota BETWEEN 1 AND 5",
            name="ck_avaliacoes_nota_range",
        ),
        sa.ForeignKeyConstraint(
            ["local_id"],
            ["locais_turisticos.id"],
            name="fk_avaliacoes_local_id_locais_turisticos",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_avaliacoes_local_id",
        "avaliacoes",
        ["local_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop evaluation and tourist location tables."""
    op.drop_table("avaliacoes")
    op.drop_table("locais_turisticos")
