from .database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
#from sqlalchemy.sql.sqltypes import Timestamp

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=False)
    password = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    is_manager = Column(Boolean, default=False)
    is_member = Column(Boolean, default=False)
    is_staff = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=True)
