"""wallets to members, transaction origin, and contribution day table

Revision ID: 569f3461f673
Revises: 4e61a2838da7
Create Date: 2024-04-16 09:48:43.458261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '569f3461f673'
down_revision: Union[str, None] = '4e61a2838da7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('chama_contribution_day',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chama_id', sa.Integer(), nullable=True),
    sa.Column('next_contribution_date', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['chama_id'], ['chamas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chama_contribution_day_id'), 'chama_contribution_day', ['id'], unique=False)
    op.add_column('members', sa.Column('wallet_balance', sa.Integer(), nullable=True))
    op.add_column('transactions', sa.Column('transaction_origin', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('transactions', 'transaction_origin')
    op.drop_column('members', 'wallet_balance')
    op.drop_index(op.f('ix_chama_contribution_day_id'), table_name='chama_contribution_day')
    op.drop_table('chama_contribution_day')
    # ### end Alembic commands ###