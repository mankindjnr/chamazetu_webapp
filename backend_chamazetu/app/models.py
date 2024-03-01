from .database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Table
from sqlalchemy.orm import relationship
from datetime import datetime

# a many to many relationship - association table between members and chamas
member_chama = Table(
    "member_chama",
    Base.metadata,
    Column("member_id", Integer, ForeignKey("members.id")),
    Column("chama_id", Integer, ForeignKey("chamas.id")),
)


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    password = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    # for manager to assign an assistant # TODO: add this to the managers dashboard-they can assign already existing members to be staff
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    # defining the relationship to chama
    chamas = relationship(
        "Chama", secondary=member_chama, back_populates="members", lazy="dynamic"
    )
    transaction_sent = relationship(
        "Transaction", back_populates="sender", foreign_keys="Transaction.sender_id"
    )
    transaction_received = relationship(
        "Transaction",
        back_populates="recepient",
        foreign_keys="Transaction.recepient_id",
    )


class Manager(Base):
    __tablename__ = "managers"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    password = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    # for manager to assign an assistant # TODO: add this to the managers dashboard-they can assign already existing members to be staff
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    # defining relationship to transaction
    chamas = relationship("Chama", back_populates="manager")


# many to many relation between users and chamas where users can be in many chamas and chamas can have many users
class Chama(Base):
    __tablename__ = "chamas"

    id = Column(Integer, primary_key=True)
    chamaname = Column(String(100), nullable=False, unique=True, index=True)
    manage_id = Column(Integer, ForeignKey("managers.id"))
    member_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=True)  # blue checkmark for legacy groups
    description = Column(String(250), nullable=False)

    # defining the relationship to user
    members = relationship(
        "Member", secondary=member_chama, back_populates="chamas", lazy="dynamic"
    )
    manager = relationship("Manager", back_populates="chamas")
    transactions = relationship("Transaction", back_populates="recepient")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    sender = relationship(
        "Member", back_populates="transaction_sent", foreign_keys=[sender_id]
    )
    recepient_id = Column(Integer, ForeignKey("chamas.id"), nullable=False)
    recepient = relationship("Chama", back_populates="transactions")
    amount = Column(Integer, nullable=False)
    sent_at = Column(DateTime, default=datetime.now)
    is_reversed = Column(Boolean, default=False)
