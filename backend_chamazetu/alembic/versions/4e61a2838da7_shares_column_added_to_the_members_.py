"""shares column added to the members_chamas association table

Revision ID: 4e61a2838da7
Revises: 50d3e2221226
Create Date: 2024-04-15 10:33:31.520732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e61a2838da7'
down_revision: Union[str, None] = '50d3e2221226'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###