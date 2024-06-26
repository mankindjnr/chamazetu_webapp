"""from integer to float

Revision ID: 3f4c1dfee6bb
Revises: 288dba193c1e
Create Date: 2024-06-17 12:34:33.811536

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f4c1dfee6bb"
down_revision: Union[str, None] = "288dba193c1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        table_name="investments_performance",
        column_name="amount_invested",
        type_=sa.Float,
        existing_type=sa.Integer,
    )


def downgrade() -> None:
    op.alter_column(
        table_name="investments_performance",
        column_name="amount_invested",
        type_=sa.Integer,
        existing_type=sa.Float,
    )
