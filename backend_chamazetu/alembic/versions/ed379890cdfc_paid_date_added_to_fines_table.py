"""paid date added to fines table

Revision ID: ed379890cdfc
Revises: 98622185b67c
Create Date: 2024-06-19 09:25:02.778568

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ed379890cdfc'
down_revision: Union[str, None] = '98622185b67c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('fines', sa.Column('paid_date', sa.DateTime(), nullable=True))
    op.alter_column('fines', 'fine_date',
               existing_type=postgresql.TIMESTAMP(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('fines', 'fine_date',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
    op.drop_column('fines', 'paid_date')
    # ### end Alembic commands ###
