"""fulfillment date addded to mmf withdrawal

Revision ID: 4845b28ab605
Revises: f52bdea22ab3
Create Date: 2024-07-01 08:50:48.815055

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4845b28ab605"
down_revision: Union[str, None] = "f52bdea22ab3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chama_mmf_withdrawals",
        sa.Column("fulfilled_date", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chama_mmf_withdrawals", "fulfilled_date")
