"""callback data recorded

Revision ID: 55ff5bcad67d
Revises: 4845b28ab605
Create Date: 2024-07-04 11:58:17.436190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55ff5bcad67d'
down_revision: Union[str, None] = '4845b28ab605'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('callback_data',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('MerchantRequestID', sa.String(), nullable=False),
    sa.Column('CheckoutRequestID', sa.String(), nullable=False),
    sa.Column('ResultCode', sa.Integer(), nullable=False),
    sa.Column('ResultDesc', sa.String(), nullable=False),
    sa.Column('Amount', sa.Integer(), nullable=False),
    sa.Column('MpesaReceiptNumber', sa.String(), nullable=False),
    sa.Column('TransactionDate', sa.DateTime(), nullable=False),
    sa.Column('PhoneNumber', sa.String(length=12), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_callback_data_id'), 'callback_data', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_callback_data_id'), table_name='callback_data')
    op.drop_table('callback_data')
    # ### end Alembic commands ###
