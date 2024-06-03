"""added column first contribution date

Revision ID: 4be2a36d19cf
Revises: 76832edab769
Create Date: 2024-05-30 00:54:04.813716

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4be2a36d19cf"
down_revision: Union[str, None] = "76832edab769"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server default will be the current timestamp - new column with default
    op.add_column(
        "chamas",
        sa.Column(
            "first_contribution_date",
            sa.DateTime,
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    # remove the server default and set the column as non nullable
    op.alter_column(
        "chamas", "first_contribution_date", nullable=False, server_default=None
    )


def downgrade() -> None:
    # remove the column
    op.drop_column("chamas", "first_contribution_date")
