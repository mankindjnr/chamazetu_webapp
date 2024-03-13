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
    chama_name = Column(String, index=True, nullable=False)
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
    is_active = Column(
        Boolean, default=False
    )  # chama is active on start cycle day (auto/manual)
    accepting_members = Column(Boolean, default=True)  # chama is accepting new members
    start_cycle = Column(DateTime, nullable=False)
    end_cycle = Column(DateTime, nullable=False)
    is_deleted = Column(Boolean, default=False)
    verified_chama = Column(Boolean, default=True)  # bluecheckmark -reputable manager

    # Define the one-to-many relationship between chama and transactions(1 chama can have many transactions)
    transactions = relationship("Transaction", back_populates="chama")
    # Define the one-to-many relationship between manager and chamas(1 manager can have many chamas)
    manager_id = Column(Integer, ForeignKey("managers.id"))
    manager = relationship("Manager", back_populates="chamas")
    # Define the many-to-many relationship between members and chamas(many members can belong to many chamas)
    members = relationship(
        "Member", secondary=members_chamas_association, back_populates="chamas"
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
    date_of_transaction = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    transaction_completed = Column(Boolean, default=False)
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
