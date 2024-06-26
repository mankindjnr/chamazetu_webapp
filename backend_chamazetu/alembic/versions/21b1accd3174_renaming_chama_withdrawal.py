"""renaming chama withdrawal

Revision ID: 21b1accd3174
Revises: 3f4c1dfee6bb
Create Date: 2024-06-18 08:43:55.861144

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "21b1accd3174"
down_revision: Union[str, None] = "3f4c1dfee6bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("chama_withdrawals", "chama_mmf_withdrawals")


def downgrade() -> None:
    op.rename_table("chama_mmf_withdrawals", "chama_withdrawals")
