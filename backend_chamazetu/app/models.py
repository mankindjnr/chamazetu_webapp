from .database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from datetime import timezone

# Define the many-to-many relationship table between members and chamas
members_chamas_association = Table(
    "members_chamas",
    Base.metadata,
    Column("member_id", Integer, ForeignKey("members.id")),
    Column("chama_id", Integer, ForeignKey("chamas.id")),
)

# Define the many-to-many relationship table between chamas and investments one chama can have many investments and one investment can belong to many chamas
chama_investment_association = Table(
    "chama_investment",
    Base.metadata,
    Column("chama_id", Integer, ForeignKey("chamas.id")),
    Column("investment_id", Integer, ForeignKey("investments.id")),
)


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    email_verified = Column(Boolean, default=False)
    password = Column(String, nullable=False)
    date_joined = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    is_active = Column(Boolean, default=True)
    is_member = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)

    # Define the one-to-many relationship between member and transactions(1 member can have many transactions)
    transactions = relationship("Transaction", back_populates="member")
    # Define the many-to-many relationship between members and chamas(many members can belong to many chamas)
    chamas = relationship(
        "Chama", secondary=members_chamas_association, back_populates="members"
    )


class Chama(Base):
    __tablename__ = "chamas"

    id = Column(Integer, primary_key=True, index=True)
    chama_name = Column(String, index=True, unique=True, nullable=False)
    chama_type = Column(String, nullable=False)  # investment, savings, lending
    num_of_members_allowed = Column(String, nullable=False)
    description = Column(String, nullable=False)
    date_created = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    registration_fee = Column(Integer, nullable=False)
    contribution_amount = Column(Integer, nullable=False)
    contribution_interval = Column(
        String, nullable=False
    )  # daily, weekly, monthly, custom
    contribution_day = Column(String, nullable=False)  # tuesday, friday, 1st, 15th
    is_active = Column(
        Boolean, default=False
    )  # chama is active on start cycle day (auto/manual)
    accepting_members = Column(
        Boolean, nullable=False
    )  # chama is accepting new members
    start_cycle = Column(DateTime, nullable=False)
    restart = Column(Boolean, default=False)  # chama has restarted
    is_deleted = Column(Boolean, default=False)
    verified_chama = Column(Boolean, default=True)  # bluecheckmark -reputable manager

    rules = relationship("Rule", back_populates="chama")
    faqs = relationship("Faq", back_populates="chama")

    # Define the one-to-many relationship between chama and transactions(1 chama can have many transactions)
    transactions = relationship("Transaction", back_populates="chama")
    # Define the one-to-many relationship between manager and chamas(1 manager can have many chamas)
    manager_id = Column(Integer, ForeignKey("managers.id"))
    manager = relationship("Manager", back_populates="chamas")
    # Define the many-to-many relationship between members and chamas(many members can belong to many chamas)
    members = relationship(
        "Member", secondary=members_chamas_association, back_populates="chamas"
    )
    # Define the many-to-many relationship between chamas and investments one chama can have many investments and one investment can belong to many chamas
    investments = relationship(
        "investment", secondary=chama_investment_association, back_populates="chamas"
    )


class Manager(Base):
    __tablename__ = "managers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)
    date_joined = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    is_active = Column(Boolean, default=True)
    is_manager = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)

    # Define the one-to-many relationship between manager and chamas(1 manager can have many chamas)
    chamas = relationship("Chama", back_populates="manager")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)
    phone_number = Column(String(12), nullable=False)
    date_of_transaction = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    transaction_completed = Column(Boolean, default=False)
    transaction_code = Column(
        String, nullable=False
    )  # mpesa code or bank transaction code
    transaction_type = Column(
        String, nullable=False
    )  # deposit, withdrawal, loan, loan_payment, interest
    is_reversed = Column(Boolean, default=False)

    # Define the one-to-many relationship between chama and transactions(1 chama can have many transactions)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    chama = relationship("Chama", back_populates="transactions")
    # Define the one-to-many relationship between member and transactions(1 member can have many transactions)
    member_id = Column(Integer, ForeignKey("members.id"))
    member = relationship("Member", back_populates="transactions")


class Chama_Account(Base):
    __tablename__ = "chama_accounts"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    account_balance = Column(Integer, nullable=False)
    account_status = Column(Boolean, default=False)  # active or inactive


class investment(Base):
    __tablename__ = "investments"

    id = Column(Integer, primary_key=True, index=True)
    investment_name = Column(String, nullable=False)
    investment_type = Column(String, nullable=False)
    investment_amount = Column(Integer, nullable=False)
    investment_period = Column(
        Integer, nullable=False
    )  # number of days, weeks, months, years
    investment_period_unit = Column(
        String, nullable=False
    )  # days, weeks, months, years
    investment_rate = Column(Integer, nullable=False)  # interest rate
    investment_start_date = Column(DateTime, default=datetime.now(timezone.utc))
    investment_end_date = Column(DateTime, nullable=False)
    investment_status = Column(Boolean, default=False)  # active or inactive
    investment_return = Column(
        Integer, nullable=False
    )  # amt to be returned after invest period
    investment_returned = Column(
        Boolean, default=False
    )  # has the investment been returned

    # Define the many-to-many relationship between chamas and investments
    chamas = relationship(
        "Chama", secondary=chama_investment_association, back_populates="investments"
    )


class chama_blog(Base):
    __tablename__ = "chama_blog"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("managers.id"))
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    paybill_number = Column(Integer, nullable=False)
    twitter = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    rule = Column(String, nullable=False)
    chama = relationship("Chama", back_populates="rules")


class Faq(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    chama = relationship("Chama", back_populates="faqs")


# class PasswordReset(Base):
#     __tablename__ = "password_resets"

#     id = Column(Integer, primary_key=True, index=True)
#     email = Column(String, unique=True, index=True, nullable=False)
#     token = Column(String, nullable=False)
#     date_created = Column(DateTime, default=datetime.now(timezone.utc))
#     updated_at = Column(
#         DateTime,
#         default=datetime.now(timezone.utc),
#         onupdate=datetime.now(timezone.utc),
#     )
#     is_active = Column(Boolean, default=True)
#     is_deleted = Column(Boolean, default=False)
