"""adding minimum withdrawal column to available investment

Revision ID: 719e2f4c8f43
Revises: fac30d64717f
Create Date: 2024-06-16 09:43:55.068150

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "719e2f4c8f43"
down_revision: Union[str, None] = "fac30d64717f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "available_investments",
        sa.Column(
            "min_withdrawal_amount", sa.Float, nullable=False, server_default="0.0"
        ),
    )


def downgrade() -> None:
    op.drop_column("available_investments", "min_withdrawal_amount")
