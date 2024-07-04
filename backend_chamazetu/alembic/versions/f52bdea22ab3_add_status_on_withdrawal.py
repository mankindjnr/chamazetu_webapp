"""add status on withdrawal

Revision ID: f52bdea22ab3
Revises: 63f3cfcf7f5b
Create Date: 2024-07-01 08:22:12.667070

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f52bdea22ab3"
down_revision: Union[str, None] = "63f3cfcf7f5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chama_mmf_withdrawals",
        sa.Column(
            "withdrawal_status",
            sa.String(255),
            nullable=False,
            server_default="PENDING",
        ),
    )


def downgrade() -> None:
    op.drop_column("chama_mmf_withdrawals", "withdrawal_status")
