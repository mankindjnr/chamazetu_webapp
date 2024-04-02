from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from pydantic.types import conint
from decouple import config


# ============== user =================
class UserBase(BaseModel):
    email: EmailStr
    password: str
    is_active: bool  # account is active or not
    email_verified: bool  # email verification
    role: str  # member or manager

    class Config:
        orm_mode = True
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    class Config:
        orm_mode = True
        from_attributes = True


class Response(BaseModel):
    id: int
    email: EmailStr
    activation_code: str
    created_at: datetime


class UserResp(BaseModel):
    User: List[Response]

    class Config:
        orm_mode = True


# ====================  Token  ====================
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class refreshedToken(BaseModel):
    new_access_token: str
    refreshed_token_type: str


class TokenData(BaseModel):
    username: str
    role: str


# ============== chama =================
class ChamaBase(BaseModel):
    chama_name: str
    chama_type: str
    num_of_members_allowed: str
    accepting_members: bool
    description: str
    registration_fee: int
    contribution_amount: int
    contribution_interval: str
    contribution_day: str
    start_cycle: datetime
    end_cycle: datetime
    manager_id: int

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaResp(BaseModel):
    Chama: List[ChamaBase]

    class Config:
        orm_mode = True


# ============== transaction =================
class TransactionBase(BaseModel):
    amount: int
    chama_id: int

    class Config:
        orm_mode = True
        # from_attributes = True


class TransactionResp(BaseModel):
    id: int
    amount: int
    member_id: int
    chama_id: int
    transaction_type: str
    date_of_transaction: datetime
    transaction_completed: bool

    class Config:
        orm_mode = True
