"""shares column added to the members_chamas association table

Revision ID: f0a55a019de1
Revises: 20e0f4327d63
Create Date: 2024-04-15 09:48:21.761074

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0a55a019de1'
down_revision: Union[str, None] = '20e0f4327d63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('members_chamas', sa.Column('num_of_shares', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('members_chamas', 'num_of_shares')
    # ### end Alembic commands ###