from .database import Base
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    Table,
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

# Define the many-to-many relationship table between members and chamas
members_chamas_association = Table(
    "members_chamas",
    Base.metadata,
    Column(
        "member_id", Integer, ForeignKey("members.id"), primary_key=True, index=True
    ),
    Column("chama_id", Integer, ForeignKey("chamas.id"), primary_key=True, index=True),
    Column("num_of_shares", Integer, nullable=False, default=1, index=True),
    Column("date_joined", DateTime, default=datetime.now(timezone.utc)),
    Column("registration_fee_paid", Boolean, default=False),
    UniqueConstraint("member_id", "chama_id", name="unique_member_chama"),
)

# Define the many-to-many relationship table between chamas and investments one chama can have many investments and one investment can belong to many chamas
chama_investment_association = Table(
    "chama_investment",
    Base.metadata,
    Column("chama_id", Integer, ForeignKey("chamas.id")),
    Column("available_investment_id", Integer, ForeignKey("available_investments.id")),
)


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    email_verified = Column(Boolean, default=False)
    # for kyc purposes id number(cmpared against phone num reg details)
    phone_number = Column(String(12), nullable=True)
    twitter = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)

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

    # wallet balance
    wallet_balance = Column(Integer, nullable=False, default=0)

    fines = relationship("Fine", back_populates="member")

    # one to many with wallet transactions
    wallet_transactions = relationship("Wallet_Transaction", back_populates="member")

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
    description = Column(String(500), nullable=False)
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
    contribution_day = Column(
        String, nullable=False
    )  # tuesday, friday, 1st, 15th or every first saturday of the month
    is_active = Column(
        Boolean, default=False
    )  # chama is active on start cycle day (auto/manual)
    accepting_members = Column(
        Boolean, nullable=False
    )  # chama is accepting new members
    last_joining_date = Column(DateTime, nullable=False)
    first_contribution_date = Column(DateTime, nullable=False)
    restart = Column(Boolean, default=False)  # chama has restarted
    is_deleted = Column(Boolean, default=False)
    verified_chama = Column(Boolean, default=True)  # bluecheckmark -reputable manager
    account_name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # private or public onlyy
    fine_per_share = Column(Integer, nullable=False)

    rules = relationship("Rule", back_populates="chama")
    faqs = relationship("Faq", back_populates="chama")
    fines = relationship("Fine", back_populates="chama")
    chama_contribution_day = relationship(
        "ChamaContributionDay", cascade="all,delete", back_populates="chama"
    )
    chama_mmf_withdrawals = relationship(
        "ChamaMMFWithdrawal", cascade="all,delete", back_populates="chama"
    )
    chama_accounts = relationship(
        "Chama_Account", cascade="all,delete", back_populates="chama"
    )

    # Define the one-to-many relationship between chama and transactions(1 chama can have many transactions)
    transactions = relationship("Transaction", back_populates="chama")
    # one to many relationship with investment_performance
    investments_performance = relationship(
        "Investment_Performance", back_populates="chama"
    )
    # one to many relations with mmfs transactions
    money_market_fund = relationship("MMF", back_populates="chama")
    # Define the one-to-many relationship between manager and chamas(1 manager can have many chamas)
    manager_id = Column(Integer, ForeignKey("managers.id"))
    manager = relationship("Manager", back_populates="chamas")
    # Define the many-to-many relationship between members and chamas(many members can belong to many chamas)

    daily_interest = relationship("Daily_Interest", back_populates="chama")
    monthly_interest = relationship("Monthly_Interest", back_populates="chama")

    members = relationship(
        "Member", secondary=members_chamas_association, back_populates="chamas"
    )
    # Define the many-to-many relationship between chamas and investments one chama can have many investments and one investment can belong to many chamas
    available_investments = relationship(
        "Available_Investment",
        secondary=chama_investment_association,
        back_populates="chamas",
    )


class Manager(Base):
    __tablename__ = "managers"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False)

    phone_number = Column(String(12), nullable=True)
    twitter = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)

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

    # from which account did the transaction come from - user_account, user_dynamic_wallet(global)
    transaction_origin = Column(String, nullable=False)

    # Define the one-to-many relationship between chama and transactions(1 chama can have many transactions)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    chama = relationship("Chama", back_populates="transactions")
    # Define the one-to-many relationship between member and transactions(1 member can have many transactions)
    member_id = Column(Integer, ForeignKey("members.id"))
    member = relationship("Member", back_populates="transactions")


class CallbackData(Base):
    __tablename__ = "callback_data"

    id = Column(Integer, primary_key=True, index=True)
    MerchantRequestID = Column(String, nullable=False)
    CheckoutRequestID = Column(String, nullable=False)
    ResultCode = Column(Integer, nullable=False)
    ResultDesc = Column(String, nullable=False)
    Amount = Column(Integer, nullable=False)
    MpesaReceiptNumber = Column(String, nullable=False)
    TransactionDate = Column(DateTime, nullable=False)
    PhoneNumber = Column(String(12), nullable=False)
    Purpose = Column(String, nullable=False)
    Status = Column(String, nullable=False)


class Chama_Account(Base):
    __tablename__ = "chama_accounts"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id", ondelete="CASCADE"))
    account_balance = Column(Integer, nullable=False)

    chama = relationship("Chama", back_populates="chama_accounts")


# this table carries the investments available to chamas
# access limited to admins of chamazetu to create products for customers
class Available_Investment(Base):
    __tablename__ = "available_investments"

    id = Column(Integer, primary_key=True, index=True)
    investment_name = Column(String, nullable=False)
    investment_type = Column(String, nullable=False)
    min_invest_amount = Column(Integer, nullable=False)
    min_withdrawal_amount = Column(Integer, nullable=False)
    investment_period = Column(
        Integer, nullable=False
    )  # number of days, weeks, months, years OR N/A - how long before allowing withdrawal
    investment_period_unit = Column(
        String, nullable=False
    )  # days, weeks, months, years or N/A
    investment_rate = Column(Float, nullable=False)  # interest rate
    investment_start_date = Column(DateTime, default=datetime.now(timezone.utc))
    investment_return = Column(
        Float, nullable=False
    )  # amt earned during the invest period - the interests of this investment accumulated so far. if paid, clear to zero, store monthly records - investment tracker
    investment_returned = Column(
        Boolean, default=False
    )  # has the investment been returned - have we paid interest of this investment or not
    investment_active = Column(Boolean, default=True)

    # Define the many-to-many relationship between chamas and investments
    chamas = relationship(
        "Chama",
        secondary=chama_investment_association,
        back_populates="available_investments",
    )


# this table keeps track of a chamas investment performance -how much they have invested and their returns
class Investment_Performance(Base):
    __tablename__ = "investments_performance"

    id = Column(Integer, primary_key=True, index=True)
    amount_invested = Column(Float, nullable=False)  # bg task
    investment_start_date = Column(DateTime, nullable=False)
    investment_name = Column(String, nullable=False)
    investment_type = Column(String, nullable=False)
    total_interest_earned = Column(Float, nullable=False)  # overtime
    weekly_interest = Column(Float, nullable=False)
    daily_interest = Column(Float, nullable=False)
    monthly_interest = Column(Float, nullable=False)
    # one to many relationship - one chama can have many investment performances(multiple investment-mmf/reits)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    chama = relationship("Chama", back_populates="investments_performance")


# # this table keeps track of a chamas daily interest for mmf investments
class Daily_Interest(Base):
    __tablename__ = "daily_mmf_interest"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    interest_earned = Column(Float, nullable=False)
    date_earned = Column(DateTime, default=datetime.now(timezone.utc))

    chama = relationship("Chama", back_populates="daily_interest")


# this table keeps track of monthly interest for all chamas
class Monthly_Interest(Base):
    __tablename__ = "monthly_mmf_interest"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    interest_earned = Column(Float, nullable=False)
    total_amount_invested = Column(Float, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

    chama = relationship("Chama", back_populates="monthly_interest")


# all mmf's transactions by chamas
class MMF(Base):
    __tablename__ = "money_market_fund"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)
    current_int_rate = Column(Float, nullable=False)
    transaction_date = Column(DateTime, default=datetime.now(timezone.utc))
    # one to many relationship - one chama can make multiple mmf transactions
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    chama = relationship("Chama", back_populates="money_market_fund")


# members wallet transactions
class Wallet_Transaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)  # moved, deposited, withdrawn
    transaction_date = Column(DateTime, default=datetime.now(timezone.utc))
    transaction_completed = Column(Boolean, default=False)
    transaction_code = Column(String, nullable=False)
    transaction_destination = Column(Integer, nullable=False)  # wallet, chama
    # one to many relationship - one member can make multiple wallet transactions
    member_id = Column(Integer, ForeignKey("members.id"))
    member = relationship("Member", back_populates="wallet_transactions")


# this table will have chama and its next contribution date
class ChamaContributionDay(Base):
    __tablename__ = "chama_contribution_day"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id", ondelete="CASCADE"))
    next_contribution_date = Column(DateTime, nullable=False)
    chama = relationship("Chama", back_populates="chama_contribution_day")


# this table tracks pending chama withdrawals and their last withdrawal date
class ChamaMMFWithdrawal(Base):
    __tablename__ = "chama_mmf_withdrawals"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, nullable=False)
    chama_id = Column(Integer, ForeignKey("chamas.id", ondelete="CASCADE"))
    withdrawal_date = Column(DateTime, nullable=False)
    withdrawal_completed = Column(Boolean, default=False)
    withdrawal_status = Column(String, nullable=False)
    fulfilled_date = Column(DateTime, nullable=True)
    chama = relationship("Chama", back_populates="chama_mmf_withdrawals")


class About_Chama(Base):
    __tablename__ = "about_chama"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("managers.id"))
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    twitter = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    mission = Column(String(500), nullable=True)
    vision = Column(String(500), nullable=True)


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    rule = Column(String, nullable=False)
    chama = relationship("Chama", back_populates="rules")


class Fine(Base):
    __tablename__ = "fines"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    member_id = Column(Integer, ForeignKey("members.id"))
    fine = Column(Integer, nullable=False)
    fine_reason = Column(String, nullable=False)
    fine_date = Column(DateTime, nullable=False)
    is_paid = Column(Boolean, default=False)
    paid_date = Column(DateTime, nullable=True)  # date fine was paid in total
    total_expected_amount = Column(
        Integer, nullable=False
    )  # fine + missed contribution + interest if any
    chama = relationship("Chama", back_populates="fines")
    member = relationship("Member", back_populates="fines")


class Faq(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    chama = relationship("Chama", back_populates="faqs")


class Manager_Update_Feature(Base):
    __tablename__ = "manager_updates_and_features"

    id = Column(Integer, primary_key=True, index=True)
    feature_title = Column(String(40), nullable=False)
    description = Column(String(250), nullable=False)
    feature_date = Column(DateTime, default=datetime.now(timezone.utc))


class Member_Update_Features(Base):
    __tablename__ = "member_updates_and_features"

    id = Column(Integer, primary_key=True, index=True)
    feature_title = Column(String(40), nullable=False)
    description = Column(String(250), nullable=False)
    feature_date = Column(DateTime, default=datetime.now(timezone.utc))


class NewsletterSubscription(Base):
    __tablename__ = "newsletter_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    date_subscribed = Column(DateTime, default=datetime.now(timezone.utc))
    is_subscribed = Column(Boolean, default=True)
    date_unsubscribed = Column(DateTime, nullable=True)
