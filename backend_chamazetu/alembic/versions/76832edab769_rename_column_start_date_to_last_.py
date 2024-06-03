"""rename column start_date to last_joining_date

Revision ID: 76832edab769
Revises: 339116fca7d5
Create Date: 2024-05-30 00:45:48.850385

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "76832edab769"
down_revision: Union[str, None] = "339116fca7d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("chamas", "start_cycle", new_column_name="last_joining_date")


def downgrade() -> None:
    op.alter_column("chamas", "last_joining_date", new_column_name="start_cycle")
