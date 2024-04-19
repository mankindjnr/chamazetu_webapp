from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional, List
from pydantic.types import conint
from decouple import config


# ============== user =================
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
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
    restart: bool
    is_active: bool
    manager_id: int

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaResp(BaseModel):
    Chama: List[ChamaBase]

    class Config:
        orm_mode = True


class ChamaActivateDeactivate(BaseModel):
    chama_id: int
    is_active: bool

    class Config:
        orm_mode = True


# ============== transaction =================
class TransactionBase(BaseModel):
    amount: int
    chama_id: int
    phone_number: str
    transaction_origin: str

    class Config:
        orm_mode = True
        # from_attributes = True


class WalletTransactionBase(BaseModel):
    amount: int
    transaction_destination: int

    class Config:
        orm_mode = True


class MemberWalletBalanceResp(BaseModel):
    wallet_balance: int

    class Config:
        orm_mode = True


class WalletTransactionResp(BaseModel):
    amount: int
    transaction_type: str
    transaction_completed: bool
    transaction_date: datetime
    transaction_destination: int

    class Config:
        orm_mode = True


class UpdateWalletBase(BaseModel):
    transaction_destination: int
    amount: int
    transaction_type: str

    class Config:
        orm_mode = True


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


class RecentTransactionResp(BaseModel):
    amount: int
    member_id: int
    transaction_type: str
    date_of_transaction: datetime

    class Config:
        orm_mode = True


class MemberRecentTransactionBase(BaseModel):
    member_id: int

    class Config:
        orm_mode = True


class MemberRecentTransactionResp(BaseModel):
    amount: int
    chama_id: int
    transaction_type: str
    date_of_transaction: datetime
    transaction_origin: str
    transaction_completed: bool


# ============== chama account =================
class ChamaAccountBase(BaseModel):
    chama_id: int
    amount_deposited: int
    transaction_type: str

    class Config:
        orm_mode = True


class ChamaAccountResp(BaseModel):
    chama_id: int
    account_balance: int

    class Config:
        orm_mode = True


# ============== shares =================


class ChamaMemberSharesBase(BaseModel):
    chama_id: int
    num_of_shares: int

    class Config:
        orm_mode = True


class MemberSharesBase(BaseModel):
    member_id: int
    chama_id: int

    class Config:
        orm_mode = True


class MemberSharesResp(BaseModel):
    member_expected_contribution: int

    class Config:
        orm_mode = True


# =========== updated password =================
class UpdatePasswordBase(BaseModel):
    email: str
    updated_password: str


# =========== invest ===========================
class InvestBase(BaseModel):
    chama_id: int
    amount: int
    transaction_type: str


class InvestmentPerformanceResp(BaseModel):
    chama_id: int
    amount_invested: int


# ============ update investment account =========
class UpdateInvestmentAccountBase(BaseModel):
    amount_invested: int
    investment_type: str
    transaction_type: str
    chama_id: int


# ============ members ==========================
class MemberContributionBase(BaseModel):
    chama_id: int
    member_id: int
    upcoming_contribution_date: str
    previous_contribution_date: str

    class Config:
        orm_mode = True


class MemberContributionResp(BaseModel):
    member_contribution: int

    class Config:
        orm_mode = True
