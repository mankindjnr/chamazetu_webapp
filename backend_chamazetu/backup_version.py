"""pitch day prep tables                                                                                                                                                                                                         
                                                                                                                                                                                                                                 
Revision ID: c852aad8ed17                                                                                                                                                                                                        
Revises: 6832869ee948                                                                                                                                                                                                            
Create Date: 2024-11-20 16:11:53.657857                                                                                                                                                                                          
                                                                                                                                                                                                                                 
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.                                                                                                                                                                                         
revision: str = 'c852aad8ed17'
down_revision: Union[str, None] = '6832869ee948'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###                                                                                                                                                                
    op.create_table('investment_marketplace',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('investment_title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('suitable_activities', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('thumbnail', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investment_marketplace_id'), 'investment_marketplace', ['id'], unique=False)
    op.create_table('chama_investment_marketplace',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chama_id', sa.Integer(), nullable=False),
    sa.Column('investment_marketplace_id', sa.Integer(), nullable=False),
    sa.Column('investment_amount', sa.Float(), nullable=False),
    sa.Column('investment_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['chama_id'], ['chamas.id'], ),
    sa.ForeignKeyConstraint(['investment_marketplace_id'], ['investment_marketplace.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chama_investment_marketplace_chama_id'), 'chama_investment_marketplace', ['chama_id'], unique=False)
    op.create_index(op.f('ix_chama_investment_marketplace_id'), 'chama_investment_marketplace', ['id'], unique=False)
    op.create_index(op.f('ix_chama_investment_marketplace_investment_marketplace_id'), 'chama_investment_marketplace', ['investment_marketplace_id'], unique=False)
    op.create_table('table_banking_dividend_disbursement',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('user_name', sa.String(), nullable=False),
    sa.Column('shares', sa.Integer(), nullable=False),
    sa.Column('dividend_amount', sa.Float(), nullable=False),
    sa.Column('principal_amount', sa.Float(), nullable=False),
    sa.Column('disbursement_date', sa.DateTime(), nullable=True),
    sa.Column('cycle_number', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_table_banking_dividend_disbursement_activity_id'), 'table_banking_dividend_disbursement', ['activity_id'], unique=False)
    op.create_index(op.f('ix_table_banking_dividend_disbursement_id'), 'table_banking_dividend_disbursement', ['id'], unique=False)
    op.create_index(op.f('ix_table_banking_dividend_disbursement_user_id'), 'table_banking_dividend_disbursement', ['user_id'], unique=False)
    op.alter_column('table_banking_dividends', 'chama_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('table_banking_dividends', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('table_banking_loan_eligibility', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('table_banking_loan_eligibility', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('table_banking_loan_management', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('table_banking_loan_settings', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('table_banking_requested_loans', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('table_banking_requested_loans', 'rejected',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    # ### end Alembic commands ### 

def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###                                                                                                                                                                
    op.alter_column('table_banking_requested_loans', 'rejected',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('table_banking_requested_loans', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('table_banking_loan_settings', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('table_banking_loan_management', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('table_banking_loan_eligibility', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('table_banking_loan_eligibility', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('table_banking_dividends', 'activity_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('table_banking_dividends', 'chama_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint('unique_chama_user_relationship', 'chamas_users', type_='unique')
    op.drop_constraint('unique_activity_user_relationship', 'activities_users', type_='unique')
    op.drop_index(op.f('ix_table_banking_dividend_disbursement_user_id'), table_name='table_banking_dividend_disbursement')
    op.drop_index(op.f('ix_table_banking_dividend_disbursement_id'), table_name='table_banking_dividend_disbursement')
    op.drop_index(op.f('ix_table_banking_dividend_disbursement_activity_id'), table_name='table_banking_dividend_disbursement')
    op.drop_table('table_banking_dividend_disbursement')
    op.drop_index(op.f('ix_chama_investment_marketplace_investment_marketplace_id'), table_name='chama_investment_marketplace')
    op.drop_index(op.f('ix_chama_investment_marketplace_id'), table_name='chama_investment_marketplace')
    op.drop_index(op.f('ix_chama_investment_marketplace_chama_id'), table_name='chama_investment_marketplace')
    op.drop_table('chama_investment_marketplace')
    op.drop_index(op.f('ix_investment_marketplace_id'), table_name='investment_marketplace')
    op.drop_table('investment_marketplace')
    # ### end Alembic commands ### 