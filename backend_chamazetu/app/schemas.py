from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional, List, Union
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


class UserEmailActvationBase(BaseModel):
    user_email: EmailStr

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
    restart: bool
    is_active: bool
    manager_id: int
    category: str
    fine_per_share: int
    last_joining_date: datetime
    first_contribution_date: datetime

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


class ActivelyAcceptingMembersChamas(BaseModel):
    manager_id: int
    chama_type: str
    chama_name: str
    id: int

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaDescription(BaseModel):
    chama_id: int
    description: str

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaVision(BaseModel):
    chama_id: int
    vision: str

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaMission(BaseModel):
    chama_id: int
    mission: str

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaRuleBase(BaseModel):
    chama_id: int
    rule: str

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaRuleDeleteBase(BaseModel):
    chama_id: int
    rule_id: int

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaFaqBase(BaseModel):
    chama_id: int
    question: str
    answer: str

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaFaqDeleteBase(BaseModel):
    chama_id: int
    faq_id: int

    class Config:
        orm_mode = True
        from_attributes = True


class ChamaDeleteBase(BaseModel):
    chama_id: int

    class Config:
        orm_mode = True
        from_attributes = True


# ============== transaction =================
class TransactionBase(BaseModel):
    amount: int
    chama_id: int
    phone_number: str
    transaction_origin: str

    class Config:
        orm_mode = True
        # from_attributes = True

class DirectTransactionBase(BaseModel):
    amount: int
    member_id: int
    chama_id: int
    phone_number: str
    transaction_origin: str
    transaction_code: str

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
    transaction_code: str

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


class WithdrawBase(BaseModel):
    chama_id: int
    amount: int

    class Config:
        orm_mode = True


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


class ChangePasswordBase(BaseModel):
    user_id: int
    old_password: str
    new_password: str


# =========== invest ===========================
class InvestBase(BaseModel):
    chama_id: int
    amount: int
    transaction_type: str
    investment_type: str


class InvestmentPerformanceResp(BaseModel):
    chama_id: int
    amount_invested: float
    daily_interest: float
    weekly_interest: float
    monthly_interest: float
    total_interest_earned: float
    investment_rate: float


# ============ update investment account =========
class UpdateInvestmentAccountBase(BaseModel):
    amount_invested: int
    investment_type: str
    transaction_type: str
    chama_id: int


class AvailableInvestmentResp(BaseModel):
    investment_name: str
    investment_type: str
    min_invest_amount: int
    investment_period: int
    investment_period_unit: str
    investment_rate: float
    investment_active: bool


# ============ members ==========================
class MemberChamasResp(BaseModel):
    chama_name: str
    chama_type: str
    contribution_interval: str

    class Config:
        orm_mode = True
        from_attributes = True


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


class ChamaMembersList(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    twitter: Union[str, None]
    facebook: Union[str, None]
    linkedin: Union[str, None]
    profile_picture: Union[str, None]

    class Config:
        orm_mode = True
        from_attributes = True


# ============= manager =========================
class ManagerChamasResp(BaseModel):
    chama_name: str
    is_active: bool

    class Config:
        orm_mode = True
        from_attributes = True


# ============ INterests =========================
class Limit(BaseModel):
    limit: int


class DailyInterestResp(BaseModel):
    daily_interest: float
    date_earned: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class MonthlyInterestResp(BaseModel):
    interest_earned: float
    month: int
    year: int
    total_amount_invested: float

    class Config:
        orm_mode = True
        from_attributes = True


# ============ users profile update =========================
class SuccessBase(BaseModel):
    message: str

    class Config:
        orm_mode = True
        from_attributes = True


class PhoneNumberBase(BaseModel):
    phone_number: str

    class Config:
        orm_mode = True
        from_attributes = True


class TwitterBase(BaseModel):
    twitter: str

    class Config:
        orm_mode = True
        from_attributes = True


class FacebookBase(BaseModel):
    facebook: str

    class Config:
        orm_mode = True
        from_attributes = True


class LinkedinBase(BaseModel):
    linkedin: str

    class Config:
        orm_mode = True
        from_attributes = True


class ProfilePicture(BaseModel):
    profile_picture_name: str

    class Config:
        orm_mode = True
        from_attributes = True


class ProfileUpdateBase(BaseModel):
    phone_number: str
    twitter: str
    facebook: str
    linkedin: str

    class Config:
        orm_mode = True
        from_attributes = True


class NewsletterSubscription(BaseModel):
    email: EmailStr

    class Config:
        orm_mode = True
        from_attributes = True


class NewsletterSubscriptionResp(BaseModel):
    email: EmailStr
    date_subscribed: datetime

    class Config:
        orm_mode = True
        from_attributes = True


# ============ Daraja API=========================
class StkPushBase(BaseModel):
    phone_number: str
    amount: int
    recipient: str
    description: str

    class Config:
        orm_mode = True
        from_attributes = True


class StkPushStatusBase(BaseModel):
    checkout_request_id: str

    class Config:
        orm_mode = True
        from_attributes = True


class CallbackData(BaseModel):
    Body: str
    TransactionType: str
    TransID: str
    TransTime: str
    TransAmount: str
    BusinessShortCode: str
    BillRefNumber: str
    InvoiceNumber: str
    OrgAccountBalance: str
    ThirdPartyTransID: str
    MSISDN: str
    FirstName: str
    MiddleName: str
    LastName: str

    class Config:
        orm_mode = True
        from_attributes = True


# =========== fine ==============
class MemberFineBase(BaseModel):
    member_id: int
    chama_id: int
    amount: int

    class Config:
        orm_mode = True
        from_attributes = True


class MemberFineResp(BaseModel):
    balance_after_fines: int

    class Config:
        orm_mode = True
        from_attributes = True


class MemberFines(BaseModel):
    member_id: int
    chama_id: int

    class Config:
        orm_mode = True
        from_attributes = True


class MemberFinesResp(BaseModel):
    has_fines: bool

    class Config:
        orm_mode = True
        from_attributes = True


class MpesaPayFinesBase(BaseModel):
    amount: int
    transaction_destination: int
    phone_number: str
    transaction_code: str
    member_id: int

    class Config:
        orm_mode = True
        from_attributes = True


class TotalFinesResp(BaseModel):
    total_fines: int

    class Config:
        orm_mode = True
        from_attributes = True
