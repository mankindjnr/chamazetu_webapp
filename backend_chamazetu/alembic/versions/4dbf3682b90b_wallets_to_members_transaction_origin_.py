"""wallets to members, transaction origin, and contribution day table

Revision ID: 4dbf3682b90b
Revises: 5d72fec8506f
Create Date: 2024-04-16 11:00:13.222439

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dbf3682b90b'
down_revision: Union[str, None] = '5d72fec8506f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('members', 'wallet_balance',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('transactions', 'transaction_origin',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('transactions', 'transaction_origin',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('members', 'wallet_balance',
               existing_type=sa.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###