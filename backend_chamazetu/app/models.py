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
    func,
    event,
    Sequence,
)
from sqlalchemy.orm import relationship
from .database import Base, SessionLocal
from datetime import datetime
from pytz import timezone
import string
import random
import sqlalchemy as sa

nairobi_tz = timezone("Africa/Nairobi")


def nairobi_now():
    return datetime.now(nairobi_tz).replace(tzinfo=None)


user_id_seq = Sequence("user_id_seq", start=940, increment=1)
wallet_id_seq = Sequence("wallet_id_seq", start=470, increment=1)
chama_code_seq = Sequence("chama_code_seq", start=490, increment=3)

# define the many-to-many relationship table between chamas and users
# add is_manager, is_member, is_secretary, is_signatory, is_treasurer, is_chairman, is_vice_chairman, is_organizer, is_member, is_admin, is_super_admin
chama_user_association = Table(
    "chamas_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True, index=True),
    Column("chama_id", Integer, ForeignKey("chamas.id"), primary_key=True, index=True),
    Column("date_joined", DateTime, default=nairobi_now),
    Column("registration_fee_paid", Boolean, default=False),
    UniqueConstraint("user_id", "chama_id", name="unique_chama_user_relationship"),
)

# define the many-to-many relationship table between activities and users
# where users can join multiple activities and activities can have multiple users
activity_user_association = Table(
    "activities_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True, index=True),
    Column(
        "activity_id",
        Integer,
        ForeignKey("activities.id"),
        primary_key=True,
        index=True,
    ),
    Column("shares", Integer, nullable=False, default=1, index=True),
    Column("share_value", Integer, nullable=False, default=0, index=True),
    Column("date_joined", DateTime, default=nairobi_now),
    Column("is_active", Boolean, default=True),
    Column("is_deleted", Boolean, default=False),
    UniqueConstraint(
        "user_id", "activity_id", name="unique_activity_user_relationship"
    ),
)

# relationship between chamas and signatories/secrataries/treasurers/chairman/vice_chairman/organizers - one table


# Define the many-to-many relationship table between chamas and investments one chama can have many investments and one investment can belong to many chamas
chama_investment_association = Table(
    "chama_investment",
    Base.metadata,
    Column("chama_id", Integer, ForeignKey("chamas.id")),
    Column("available_investment_id", Integer, ForeignKey("available_investments.id")),
)


# user model to replace the member and manager models below
# TODO:user id to nulable false after production
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        String,
        nullable=True,
        unique=True,
        index=True,
        default=lambda: f"940{next_user_id}",
    )
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    email_verified = Column(Boolean, default=False)
    phone_number = Column(String(12), nullable=True)
    twitter = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    profile_picture = Column(String, nullable=True)
    password = Column(String, nullable=False)
    date_joined = Column(DateTime, default=nairobi_now)
    updated_at = Column(
        DateTime,
        default=nairobi_now,
        onupdate=nairobi_now,
    )
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)

    wallet_balance = Column(Integer, nullable=False, default=0)
    wallet_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
        default=lambda: f"W470{next_wallet_id}",
    )
    zetucoins = Column(Integer, nullable=False, default=0)
    auto_contributions = relationship("AutoContribution", back_populates="user")
    wallet_transactions = relationship("WalletTransaction", back_populates="user")
    chamas = relationship(
        "Chama", secondary=chama_user_association, back_populates="user"
    )
    managed_chamas = relationship("Chama", back_populates="manager")
    activities = relationship("Activity", back_populates="manager")
    activities = relationship(
        "Activity", secondary=activity_user_association, back_populates="users"
    )
    activities_transactions = relationship("ActivityTransaction", back_populates="user")
    activity_fines = relationship("ActivityFine", back_populates="user")
    chama_invites = relationship("ChamaInvite", back_populates="user")
    activity_invites = relationship("ActivityInvite", back_populates="user")
    rotation_order = relationship("RotationOrder", back_populates="recipient")
    contributed_rotations = relationship(
        "RotatingContributions",
        foreign_keys="RotatingContributions.contributor_id",
        back_populates="contributor",
    )
    received_rotations = relationship(
        "RotatingContributions",
        foreign_keys="RotatingContributions.recipient_id",
        back_populates="recipient",
    )
    late_contributions = relationship(
        "LateRotationDisbursements",
        foreign_keys="LateRotationDisbursements.late_contributor_id",
    )
    late_disbursements = relationship(
        "LateRotationDisbursements",
        foreign_keys="LateRotationDisbursements.late_recipient_id",
    )
    table_banking_requested_loans = relationship(
        "TableBankingRequestedLoans", back_populates="user"
    )
    table_banking_loan_eligibility = relationship(
        "TableBankingLoanEligibility", back_populates="user"
    )


class Chama(Base):
    __tablename__ = "chamas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chama_code = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
        default=lambda: f"490{next_chama_code}",
    )
    chama_name = Column(String, index=True, unique=True, nullable=False)
    chama_type = Column(String, nullable=False)  # investment, savings, lending
    num_of_members_allowed = Column(String, nullable=False)
    description = Column(String(500), nullable=False)
    date_created = Column(DateTime, nullable=False, default=nairobi_now)
    updated_at = Column(DateTime, nullable=False, default=nairobi_now)
    is_active = Column(Boolean, nullable=False, default=True)
    registration_fee = Column(Integer, nullable=False)
    accepting_members = Column(Boolean, nullable=False, default=True)
    last_joining_date = Column(DateTime, nullable=False)
    restart = Column(Boolean, default=False)  # chama has restarted
    restart_date = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    verified_chama = Column(Boolean, default=True)  # bluecheckmark -reputable manager
    category = Column(String, nullable=False)  # private or public onlyy
    manager_id = Column(Integer, ForeignKey("users.id"))

    # relationships
    manager = relationship("User", back_populates="managed_chamas")
    activities = relationship("Activity", back_populates="chama")
    activity_contribution_date = relationship(
        "ActivityContributionDate", back_populates="chama"
    )
    user = relationship(
        "User", secondary=chama_user_association, back_populates="chamas"
    )
    rules = relationship("Rule", back_populates="chama")
    faqs = relationship("Faq", back_populates="chama")
    chama_contribution_day = relationship(
        "ChamaContributionDay", cascade="all,delete", back_populates="chama"
    )
    chama_mmf_withdrawals = relationship(
        "ChamaMMFWithdrawal", cascade="all,delete", back_populates="chama"
    )
    chama_accounts = relationship(
        "Chama_Account", cascade="all,delete", back_populates="chama"
    )
    investments_performance = relationship(
        "Investment_Performance", back_populates="chama"
    )
    money_market_fund = relationship("MMF", back_populates="chama")
    daily_interest = relationship("Daily_Interest", back_populates="chama")
    monthly_interest = relationship("Monthly_Interest", back_populates="chama")
    available_investments = relationship(
        "Available_Investment",
        secondary=chama_investment_association,
        back_populates="chamas",
    )
    activity_fines = relationship("ActivityFine", back_populates="chama")
    chama_invites = relationship("ChamaInvite", back_populates="chama")
    rotation_order = relationship("RotationOrder", back_populates="chama")
    rotating_contributions = relationship(
        "RotatingContributions", back_populates="chama"
    )
    late_rotation_disbursements = relationship(
        "LateRotationDisbursements", back_populates="chama"
    )
    chama_late_joining = relationship("ChamaLateJoining", back_populates="chama")
    table_banking_dividends = relationship(
        "TableBankingDividend", back_populates="chama"
    )


# listen to the before_insert event to automatically set chama_code
@event.listens_for(Chama, "before_insert")
def set_chama_code(mapper, connection, target):
    next_chama_code = connection.execute(
        sa.text("SELECT nextval('chama_code_seq')")
    ).scalar()
    target.chama_code = f"CH490{next_chama_code}"


# listen to the before_insert event to automatically set user_id
@event.listens_for(User, "before_insert")
def set_user_id(mapper, connection, target):
    next_user_id = connection.execute(user_id_seq)
    target.user_id = f"940{next_user_id}"


@event.listens_for(User, "before_insert")
def set_wallet_id(mapper, connection, target):
    next_wallet_id = connection.execute(wallet_id_seq)
    # random 2letters
    letters = string.ascii_uppercase
    random_letters = "".join(random.choice(letters) for i in range(2))
    target.wallet_id = f"W{random_letters}4{next_wallet_id}"


# activities created by manager for members in a chama
class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    manager_id = Column(Integer, ForeignKey("users.id"))
    activity_title = Column(String, nullable=False)
    activity_type = Column(String, nullable=False)
    # make description nullable
    activity_description = Column(String, nullable=False)
    activity_amount = Column(Integer, nullable=False)
    fine = Column(Integer, nullable=False)
    frequency = Column(String, nullable=False)
    interval = Column(String, nullable=False)
    contribution_day = Column(String, nullable=False)
    restart = Column(Boolean, default=False)
    restart_date = Column(DateTime, nullable=True)
    accepting_members = Column(Boolean, nullable=False, default=True)
    first_contribution_date = Column(DateTime, nullable=False, default=nairobi_now)
    last_joining_date = Column(DateTime, nullable=False, default=nairobi_now)
    creation_date = Column(DateTime, nullable=False, default=nairobi_now)
    updated_at = Column(DateTime, nullable=False, default=nairobi_now)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, default=False)
    mandatory = Column(Boolean, default=False)

    # relationships
    chama = relationship("Chama", back_populates="activities")
    manager = relationship("User", back_populates="activities")
    auto_contributions = relationship("AutoContribution", back_populates="activity")
    activity_contribution_date = relationship(
        "ActivityContributionDate", cascade="all,delete", back_populates="activity"
    )
    users = relationship(
        "User", secondary=activity_user_association, back_populates="activities"
    )
    activity_accounts = relationship("Activity_Account", back_populates="activity")
    activities_transactions = relationship(
        "ActivityTransaction", back_populates="activities"
    )
    activity_fines = relationship("ActivityFine", back_populates="activity")
    activity_invites = relationship("ActivityInvite", back_populates="activity")
    rotation_order = relationship("RotationOrder", back_populates="activity")
    rotating_contributions = relationship(
        "RotatingContributions", back_populates="activity"
    )
    late_rotation_disbursements = relationship(
        "LateRotationDisbursements", back_populates="activity"
    )
    merry_go_round_share_increase = relationship(
        "MerryGoRoundShareIncrease", back_populates="activity"
    )
    table_banking_dividends = relationship(
        "TableBankingDividend", back_populates="activity"
    )
    table_banking_loan_management = relationship(
        "TableBankingLoanManagement", back_populates="activity"
    )
    table_banking_requested_loans = relationship(
        "TableBankingRequestedLoans", back_populates="activity"
    )
    table_banking_loan_settings = relationship(
        "TableBankingLoanSettings", back_populates="activity"
    )
    table_banking_loan_eligibility = relationship(
        "TableBankingLoanEligibility", back_populates="activity"
    )


# activty accounts
class Activity_Account(Base):
    __tablename__ = "activity_accounts"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    account_balance = Column(Float, nullable=False)
    activity = relationship("Activity", back_populates="activity_accounts")


# activity contribution date tracker
class ActivityContributionDate(Base):
    __tablename__ = "activity_contribution_dates"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"), nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    activity_title = Column(String, nullable=False)
    activity_type = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    previous_contribution_date = Column(DateTime, nullable=False)
    next_contribution_date = Column(DateTime, nullable=False)

    # relationships
    chama = relationship("Chama", back_populates="activity_contribution_date")
    activity = relationship("Activity", back_populates="activity_contribution_date")


class ActivityTransaction(Base):
    __tablename__ = "activities_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, nullable=False)
    origin = Column(String, nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id"))
    transaction_date = Column(DateTime, default=nairobi_now)
    updated_at = Column(DateTime, default=nairobi_now)
    transaction_completed = Column(Boolean, default=False)
    transaction_code = Column(String, nullable=False)
    transaction_type = Column(String, nullable=False)  # deposit
    is_reversed = Column(Boolean, default=False)
    needs_reversal = Column(Boolean, default=False)

    # relationships
    user = relationship("User", back_populates="activities_transactions")
    activities = relationship("Activity", back_populates="activities_transactions")


# members wallet transactions
# deposit to wallet, wallet to wallet and withdrawal from wallet
class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, nullable=False)
    origin = Column(String, nullable=False)  # wallet_number, chama_id
    destination = Column(String, nullable=False)  # wallet_number, phone_number
    # deposited, withdrawn,received, sent
    transaction_type = Column(String, nullable=False)
    transaction_date = Column(DateTime, default=nairobi_now)
    transaction_completed = Column(Boolean, default=False)
    transaction_code = Column(String, nullable=False)

    # relationships
    user = relationship("User", back_populates="wallet_transactions")


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


# b2cresults
class B2CResults(Base):
    __tablename__ = "b2c_results"

    id = Column(Integer, primary_key=True, index=True)
    resulttype = Column(Integer, nullable=False)
    resultcode = Column(Integer, nullable=False)
    resultdesc = Column(String, nullable=False)
    originatorconversationid = Column(String, nullable=False)
    conversationid = Column(String, nullable=False)
    transactionid = Column(String, nullable=False)
    transactionamount = Column(Integer, nullable=False)
    transactionreceipt = Column(String, nullable=False)
    receiverpartypublicname = Column(String, nullable=False)
    transactioncompleteddatetime = Column(DateTime, nullable=False)
    b2cutilityaccountavailablefunds = Column(Float, nullable=False)
    b2cworkingaccountavailablefunds = Column(Float, nullable=False)
    b2crecipientisregisteredcustomer = Column(String, nullable=False)
    b2cchargespaidaccountavailablefunds = Column(Float, nullable=False)


class Chama_Account(Base):
    __tablename__ = "chama_accounts"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id", ondelete="CASCADE"))
    account_balance = Column(Float, nullable=False)
    available_balance = Column(Float, nullable=False)

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
    investment_start_date = Column(DateTime, default=nairobi_now)
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
    date_earned = Column(DateTime, default=nairobi_now)

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
    transaction_date = Column(DateTime, default=nairobi_now)
    # one to many relationship - one chama can make multiple mmf transactions
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    chama = relationship("Chama", back_populates="money_market_fund")


# auto contrbution data
class AutoContribution(Base):
    __tablename__ = "auto_contributions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    activity_id = Column(Integer, ForeignKey("activities.id"))
    expected_amount = Column(Integer, nullable=False)
    next_contribution_date = Column(DateTime, default=nairobi_now, nullable=False)

    # relationships
    activity = relationship("Activity", back_populates="auto_contributions")
    user = relationship("User", back_populates="auto_contributions")  # one to many


# this table will have chama and its next contribution date
class ChamaContributionDay(Base):
    __tablename__ = "chama_contribution_day"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id", ondelete="CASCADE"))
    next_contribution_date = Column(DateTime, default=nairobi_now, nullable=False)
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
    manager_id = Column(Integer, ForeignKey("users.id"))
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    twitter = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    mission = Column(String(500), nullable=True)
    vision = Column(String(500), nullable=True)


class ChamaInvite(Base):
    __tablename__ = "chama_invites"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    invitee_email = Column(String, nullable=False)
    invite_code = Column(String, nullable=False)
    invite_date = Column(DateTime, default=nairobi_now)
    invite_accepted = Column(Boolean, default=False)
    invite_accepted_date = Column(DateTime, nullable=True)
    invite_accepted_by = Column(Integer, ForeignKey("users.id"))
    invite_accepted_by_email = Column(String, nullable=True)

    # relationships
    chama = relationship("Chama", back_populates="chama_invites")
    user = relationship("User", back_populates="chama_invites")


class ActivityInvite(Base):
    __tablename__ = "activity_invites"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"))
    invitee_email = Column(String, nullable=False)
    invite_code = Column(String, nullable=False)
    invite_date = Column(DateTime, default=nairobi_now)
    invite_accepted = Column(Boolean, default=False)
    invite_accepted_date = Column(DateTime, nullable=True)
    invite_accepted_by = Column(Integer, ForeignKey("users.id"))
    invite_accepted_by_email = Column(String, nullable=True)

    # relationships
    activity = relationship("Activity", back_populates="activity_invites")
    user = relationship("User", back_populates="activity_invites")


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    rule = Column(String, nullable=False)
    chama = relationship("Chama", back_populates="rules")


class ActivityFine(Base):
    __tablename__ = "activity_fines"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    activity_id = Column(Integer, ForeignKey("activities.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    fine = Column(Integer, nullable=False)
    missed_amount = Column(Integer, nullable=False)
    expected_repayment = Column(Integer, nullable=False)
    fine_reason = Column(String, nullable=False)
    fine_date = Column(DateTime, nullable=False)
    is_paid = Column(Boolean, default=False)
    paid_date = Column(DateTime, nullable=True)  # date fine was paid in total

    # relationships
    chama = relationship("Chama", back_populates="activity_fines")
    user = relationship("User", back_populates="activity_fines")
    activity = relationship("Activity", back_populates="activity_fines")


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
    feature_date = Column(DateTime, default=nairobi_now)


class Member_Update_Features(Base):
    __tablename__ = "member_updates_and_features"

    id = Column(Integer, primary_key=True, index=True)
    feature_title = Column(String(40), nullable=False)
    description = Column(String(250), nullable=False)
    feature_date = Column(DateTime, default=nairobi_now)


class NewsletterSubscription(Base):
    __tablename__ = "newsletter_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    date_subscribed = Column(DateTime, default=nairobi_now)
    is_subscribed = Column(Boolean, default=True)
    date_unsubscribed = Column(DateTime, nullable=True)


class ChamazetuToMpesaFees(Base):
    __tablename__ = "chamazetu_to_mpesa_fees"

    id = Column(Integer, primary_key=True, index=True)
    from_amount = Column(Integer, nullable=False)
    to_amount = Column(Integer, nullable=False)
    b2c = Column(Integer, nullable=False)
    c2c = Column(Integer, nullable=False)
    chamazetu_to_mpesa = Column(Integer, nullable=False)
    difference = Column(Integer, nullable=False)


class ChamaZetu(Base):
    __tablename__ = "chamazetu"

    id = Column(Integer, primary_key=True, index=True)
    registration_fees = Column(Float, nullable=False)
    withdrawal_fees = Column(Float, nullable=False)
    reward_coins = Column(Float, nullable=False)


class RotationOrder(Base):
    __tablename__ = "rotation_order"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, nullable=False)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    activity_id = Column(Integer, ForeignKey("activities.id"))
    recipient_id = Column(Integer, ForeignKey("users.id"))
    share_value = Column(Integer, nullable=False)
    share_name = Column(String, nullable=False)
    receiving_date = Column(DateTime, nullable=False)
    order_in_rotation = Column(Integer, nullable=False)
    cycle_number = Column(Integer, nullable=False)
    expected_amount = Column(Integer, nullable=False)
    received_amount = Column(Integer, nullable=False)
    fulfilled = Column(Boolean, default=False)

    # relationships
    chama = relationship("Chama", back_populates="rotation_order")
    activity = relationship("Activity", back_populates="rotation_order")
    recipient = relationship("User", back_populates="rotation_order")


class RotatingContributions(Base):
    __tablename__ = "rotating_contributions"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    activity_id = Column(Integer, ForeignKey("activities.id"))
    contributor_id = Column(Integer, ForeignKey("users.id"))
    contributing_share = Column(String, nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"))
    recipient_share = Column(String, nullable=False)
    cycle_number = Column(Integer, nullable=False)
    expected_amount = Column(Integer, nullable=False)
    contributed_amount = Column(Integer, nullable=False)
    fine = Column(Integer, nullable=False)
    rotation_date = Column(DateTime, nullable=False)
    contributed_on_time = Column(Boolean, default=False)

    # relationships
    chama = relationship("Chama", back_populates="rotating_contributions")
    activity = relationship("Activity", back_populates="rotating_contributions")
    contributor = relationship(
        "User", foreign_keys=[contributor_id], back_populates="contributed_rotations"
    )
    recipient = relationship(
        "User", foreign_keys=[recipient_id], back_populates="received_rotations"
    )


class LateRotationDisbursements(Base):
    __tablename__ = "late_rotation_disbursements"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"))
    activity_id = Column(Integer, ForeignKey("activities.id"))
    late_contributor_id = Column(Integer, ForeignKey("users.id"))
    late_recipient_id = Column(Integer, ForeignKey("users.id"))
    late_contribution = Column(Integer, nullable=False)
    missed_rotation_date = Column(DateTime, nullable=False)
    disbursement_completed = Column(Boolean, default=False)

    # relationships
    chama = relationship("Chama", back_populates="late_rotation_disbursements")
    activity = relationship("Activity", back_populates="late_rotation_disbursements")
    late_contributor = relationship(
        "User", foreign_keys=[late_contributor_id], back_populates="late_contributions"
    )
    late_recipient = relationship(
        "User", foreign_keys=[late_recipient_id], back_populates="late_disbursements"
    )


class MerryGoRoundShareIncrease(Base):
    __tablename__ = "merry_go_round_share_increase"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), index=True)
    cycle_number = Column(Integer, nullable=False)
    max_shares = Column(Integer, nullable=False)
    allow_share_increase = Column(Boolean, default=False)
    allow_new_members = Column(Boolean, default=False)
    activity_amount = Column(Integer, nullable=False)
    adjustment_fee = Column(Integer, nullable=False)
    deadline = Column(DateTime, nullable=False)

    # relationships
    activity = relationship("Activity", back_populates="merry_go_round_share_increase")

class ChamaLateJoining(Base):
    __tablename__ = "chama_late_joining"

    id = Column(Integer, primary_key=True, index=True)
    chama_id = Column(Integer, ForeignKey("chamas.id"), index=True)
    late_joining_fee = Column(Integer, nullable=False)
    deadline = Column(DateTime, nullable=False)

    # relationships
    chama = relationship("Chama", back_populates="chama_late_joining")


class TableBankingDividend(Base):
    __tablename__ = "table_banking_dividends"

    id = Column(Integer, primary_key=True, index=True)

    chama_id = Column(Integer, ForeignKey("chamas.id"), index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), index=True)
    unpaid_dividend_amount = Column(Float, nullable=False)
    total_dividend_amount = Column(Float, nullable=False)
    cycle_number = Column(Integer, nullable=False)

    # relationships
    chama = relationship("Chama", back_populates="table_banking_dividends")
    activity = relationship("Activity", back_populates="table_banking_dividends")


class TableBankingLoanManagement(Base):
    __tablename__ = "table_banking_loan_management"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), index=True)
    total_loans_taken = Column(Float, nullable=False)
    unpaid_loans = Column(Float, nullable=False)
    paid_loans = Column(Float, nullable=False)
    cycle_number = Column(Integer, nullable=False)

    # relationships
    activity = relationship("Activity", back_populates="table_banking_loan_management")


class TableBankingLoanSettings(Base):
    __tablename__ = "table_banking_loan_settings"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), index=True)
    await_approval = Column(Boolean, default=False)
    interest_rate = Column(Float, nullable=False)
    grace_period = Column(Integer, nullable=False) #in days
    updated_at = Column(DateTime, default=nairobi_now)

    # relationships
    activity = relationship("Activity", back_populates="table_banking_loan_settings")

class TableBankingRequestedLoans(Base):
    __tablename__ = "table_banking_requested_loans"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), index=True)
    user_name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    requested_amount = Column(Float, nullable=False)
    standing_balance = Column(Float, nullable=False)
    missed_payments = Column(Integer, nullable=False)
    expected_interest = Column(Float, nullable=False)
    total_required = Column(Float, nullable=False)
    total_repaid = Column(Float, nullable=False)
    loan_cleared = Column(Boolean, default=False)
    request_date = Column(DateTime, default=nairobi_now)
    expected_repayment_date = Column(DateTime, nullable=False)
    repaid_date = Column(DateTime, nullable=True)
    cycle_number = Column(Integer, nullable=False)
    loan_approved = Column(Boolean, default=False)
    loan_approved_date = Column(DateTime, nullable=True)

    # relationships
    activity = relationship("Activity", back_populates="table_banking_requested_loans")
    user = relationship("User", back_populates="table_banking_requested_loans")

class TableBankingLoanEligibility(Base):
    __tablename__ = "table_banking_loan_eligibility"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    user_name = Column(String, nullable=False)
    eligible = Column(Boolean, default=False)
    loan_limit = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=nairobi_now)

    # relationships
    activity = relationship("Activity", back_populates="table_banking_loan_eligibility")
    user = relationship("User", back_populates="table_banking_loan_eligibility")