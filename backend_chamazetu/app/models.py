from .database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Table
from sqlalchemy.orm import relationship
from datetime import datetime

# from sqlalchemy.sql.sqltypes import Timestamp
# amny to many relationship between users and chamas
user_chama = Table(
    "user_chama",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("chama_id", Integer, ForeignKey("chamas.id")),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=False)
    password = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    is_manager = Column(Boolean, default=False)
    is_member = Column(Boolean, default=False)
    is_staff = Column(
        Boolean, default=False
    )  # for manager to assign an assistant # TODO: add this to the managers dashboard-they can assign already existing members to be staff
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    # defining the relationship to chama
    chamas = relationship(
        "Chama", secondary=user_chama, back_populates="users", lazy="dynamic"
    )
    # defining relationship to transaction
    user_transactions = relationship("Transaction", back_populates="user")


# many to many relation between users and chamas where users can be in many chamas and chamas can have many users
class Chama(Base):
    __tablename__ = "chamas"

    id = Column(Integer, primary_key=True)
    chamaname = Column(String(100), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=True)  # blue checkmark for legacy groups

    # defining the relationship to user
    users = relationship(
        "User", secondary=user_chama, back_populates="chamas", lazy="dynamic"
    )
    # defining relationship to transaction
    user_transactions = relationship("Transaction", back_populates="chama")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chama_id = Column(Integer, ForeignKey("chamas.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    is_reversed = Column(Boolean, default=False)

    # defining the relationship to user
    user = relationship("User", back_populates="user_transactions")
    chama = relationship("Chama", back_populates="user_transactions")
