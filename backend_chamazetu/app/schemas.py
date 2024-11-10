from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import Optional, List, Union, Literal
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

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    class Config:
        from_attributes = True


class UserEmailActvationBase(BaseModel):
    user_email: EmailStr

    class Config:
        from_attributes = True


class Response(BaseModel):
    id: int
    email: EmailStr
    activation_code: str
    created_at: datetime


class UserResp(BaseModel):
    User: List[Response]

    class Config:
        from_attributes = True


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


class receivedToken(BaseModel):
    token: str


# ============== chama =================
class ChamaBase(BaseModel):
    chama_name: str
    chama_type: str
    description: str
    num_of_members_allowed: str
    registration_fee: int
    restart: bool
    category: str
    last_joining_date: datetime

    class Config:
        from_attributes = True


class ChamaResp(BaseModel):
    Chama: List[ChamaBase]

    class Config:
        from_attributes = True


class ChamaActivity(BaseModel):
    contribution_date: date
    title: str
    type: str
    activity_id: int


class ChamaDetails(BaseModel):
    manager_id: int
    manager_profile_picture: str
    investment_balance: float
    general_account: float
    total_fines: float
    activities: List[ChamaActivity]


class ChamaDashboardResp(BaseModel):
    chama: ChamaDetails


class ChamaActivateDeactivate(BaseModel):
    chama_id: int
    is_active: bool

    class Config:
        from_attributes = True


class ActivelyAcceptingMembersChamas(BaseModel):
    manager_id: int
    chama_type: str
    chama_name: str
    id: int

    class Config:
        from_attributes = True


class ChamaDescription(BaseModel):
    chama_id: int
    description: str

    class Config:
        from_attributes = True


class ChamaVision(BaseModel):
    chama_id: int
    vision: str

    class Config:
        from_attributes = True


class ChamaMission(BaseModel):
    chama_id: int
    mission: str

    class Config:
        from_attributes = True


class ChamaRuleBase(BaseModel):
    chama_id: int
    rule: str

    class Config:
        from_attributes = True


class ChamaRuleDeleteBase(BaseModel):
    chama_id: int
    rule_id: int

    class Config:
        from_attributes = True


class ChamaFaqBase(BaseModel):
    chama_id: int
    question: str
    answer: str

    class Config:
        from_attributes = True


class ChamaFaqDeleteBase(BaseModel):
    chama_id: int
    faq_id: int

    class Config:
        from_attributes = True


class ChamaDeleteBase(BaseModel):
    chama_id: int

    class Config:
        from_attributes = True


# =============== activities =================
class ActivityBase(BaseModel):
    chama_id: int
    activity_title: str
    activity_type: str
    activity_description: str
    activity_amount: int
    fine: int
    frequency: str
    interval: str
    contribution_day: str
    mandatory: bool
    last_joining_date: str
    first_contribution_date: str

    class Config:
        from_attributes = True


class CreateActivityResp(BaseModel):
    status: str
    message: str

    class Config:
        from_attributes = True


class ActivityResp(BaseModel):
    chama_id: int
    activity_name: str
    activity_type: str
    activity_amount: int
    activity_balance: int

    class Config:
        from_attributes = True


class JoinActivityBase(BaseModel):
    shares: int

    class Config:
        from_attributes = True


class ContributeToActivityBase(BaseModel):
    expected_contribution: int
    amount: int

    class Config:
        from_attributes = True


# ============== transaction =================
class LoadWalletBase(BaseModel):
    amount: int
    unprocessed_code: str
    wallet_id: str
    transaction_origin: str
    transaction_code: str
    user_id: int

    class Config:
        from_attributes = True


class LoadWalletResp(BaseModel):
    amount: int
    transaction_code: str

    class Config:
        from_attributes = True


class WalletTransactionUni(BaseModel):
    amount: float
    transaction_type: str


class WalletDepositUni(BaseModel):
    amount: int
    transaction_type: str


class DirectDepositUni(BaseModel):
    amount: int
    phone_number: str
    transaction_origin: str


class UnifiedTransactionBase(BaseModel):
    member_id: int = Field(..., description="ID of the member")
    chama_id: int = Field(..., description="ID of the chama")
    transaction_code: str = Field(..., description="Transaction code")
    wallet_update: Optional[WalletTransactionUni] = Field(
        None, description="Details of the wallet update transaction"
    )
    direct_deposit: Optional[DirectDepositUni] = Field(
        None, description="Details of the direct deposit transaction"
    )
    wallet_deposit: Optional[WalletDepositUni] = Field(
        None, description="Details of the wallet deposit transaction"
    )

    class Config:
        from_attributes = True


class UnifiedWalletContBase(BaseModel):
    expected_contribution: int
    member_id: int
    chama_id: int
    amount: int

    class Config:
        from_attributes = True


class UnifiedWalletContResp(BaseModel):
    message: str

    class Config:
        from_attributes = True


class TransactionBase(BaseModel):
    amount: int
    chama_id: int
    phone_number: str
    transaction_origin: str

    class Config:
        from_attributes = True
        # from_attributes = True


class DirectTransactionBase(BaseModel):
    amount: int
    member_id: int
    chama_id: int
    phone_number: str
    transaction_origin: str
    transaction_code: str

    class Config:
        from_attributes = True


class BeforeProcessingBase(BaseModel):
    amount: int
    member_id: int
    chama_id: int
    phone_number: str
    transaction_origin: str
    transaction_code: str
    transaction_type: str

    class Config:
        from_attributes = True


class WalletTransactionBase(BaseModel):
    amount: int
    transaction_destination: int

    class Config:
        from_attributes = True


class UnprocessedWalletDepositBase(BaseModel):
    amount: int
    transaction_type: str
    transaction_origin: str
    transaction_destination: str
    user_id: int

    class Config:
        from_attributes = True


class UnprocessedWalletDepositResp(BaseModel):
    transaction_code: str

    class Config:
        from_attributes = True


class UnprocessedWalletWithdrawalBase(BaseModel):
    amount: int
    transaction_destination: str

    class Config:
        from_attributes = True


class UnprocessedWalletWithdrawalResp(BaseModel):
    transaction_code: str

    class Config:
        from_attributes = True


class ProcessUnprocessedWalletWithdrawalBase(BaseModel):
    amount: int
    unprocessed_transaction_code: str
    mpesa_receipt_number: str

    class Config:
        from_attributes = True


class WalletToChamaBase(BaseModel):
    amount: int
    transaction_destination: int  # chama_id
    transaction_code: str

    class Config:
        from_attributes = True


class MemberWalletBalanceResp(BaseModel):
    wallet_balance: int

    class Config:
        from_attributes = True


class WalletTransactionResp(BaseModel):
    amount: int
    transaction_type: str
    transaction_completed: bool
    transaction_date: datetime
    transaction_destination: str

    class Config:
        from_attributes = True


class UpdateWalletBase(BaseModel):
    member_id: int
    transaction_destination: str
    amount: int
    transaction_type: str
    transaction_code: str

    class Config:
        from_attributes = True


class TransactionResp(BaseModel):
    id: int
    amount: int
    member_id: int
    chama_id: int
    transaction_type: str
    date_of_transaction: datetime
    transaction_completed: bool

    class Config:
        from_attributes = True


class RecentTransactionResp(BaseModel):
    amount: int
    member_id: int
    transaction_type: str
    date_of_transaction: datetime

    class Config:
        from_attributes = True


class MemberRecentTransactionBase(BaseModel):
    member_id: int

    class Config:
        from_attributes = True


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
        from_attributes = True


# ============== chama account =================
class ChamaAccountBase(BaseModel):
    chama_id: int
    amount_deposited: int
    transaction_type: str

    class Config:
        from_attributes = True


class ChamaAccountResp(BaseModel):
    chama_id: int
    account_balance: int

    class Config:
        from_attributes = True


# ============== shares =================


class ChamaMemberSharesBase(BaseModel):
    chama_id: int
    num_of_shares: int

    class Config:
        from_attributes = True


class MemberSharesBase(BaseModel):
    member_id: int
    chama_id: int

    class Config:
        from_attributes = True


class MemberSharesResp(BaseModel):
    expected_contribution: int

    class Config:
        from_attributes = True


class ChamaMembershipBase(BaseModel):
    chama_id: int
    member_id: int

    class Config:
        from_attributes = True


class ChamaMembershipResp(BaseModel):
    is_member: bool

    class Config:
        from_attributes = True


class JoinChamaBase(BaseModel):
    chama_id: int
    user_id: int
    registration_fee: int
    unprocessed_code: str

    class Config:
        from_attributes = True

class AddMemberToChamaBase(BaseModel):
    chama_id: int
    user_id: int

    class Config:
        from_attributes = True


class UpdateCallbackData(BaseModel):
    checkoutid: str

    class Config:
        from_attributes = True


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
        from_attributes = True


class MemberContributionBase(BaseModel):
    chama_id: int
    member_id: int
    upcoming_contribution_date: str
    previous_contribution_date: str

    class Config:
        from_attributes = True


class MemberContributionResp(BaseModel):
    total_contribution: int

    class Config:
        from_attributes = True


class ChamaMembersList(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    twitter: Union[str, None]
    facebook: Union[str, None]
    linkedin: Union[str, None]
    profile_picture: Union[str, None]

    class Config:
        from_attributes = True


# ============= manager =========================
class ChamaMemberCount(BaseModel):
    chama_id: int
    chama_name: str
    member_count: int
    is_active: bool


class ManagerFeature(BaseModel):
    feature_title: str
    feature_description: str
    feature_date: datetime


class ManagerDashboardResp(BaseModel):
    manager_id: int
    user_email: EmailStr
    manager_profile_picture: Optional[str]
    chamas: List[ChamaMemberCount]
    updates_and_features: List[ManagerFeature]

    class Config:
        from_attributes = True


class ManagerChamasResp(BaseModel):
    chama_name: str
    is_active: bool

    class Config:
        from_attributes = True


class UserChama(BaseModel):
    email: EmailStr
    chama_id: int

    class Config:
        from_attributes = True


class UserActivity(BaseModel):
    email: EmailStr
    activity_id: int

    class Config:
        from_attributes = True


# ============ INterests =========================
class Limit(BaseModel):
    limit: int


class DailyInterestResp(BaseModel):
    daily_interest: float
    date_earned: datetime

    class Config:
        from_attributes = True


class MonthlyInterestResp(BaseModel):
    interest_earned: float
    month: int
    year: int
    total_amount_invested: float

    class Config:
        from_attributes = True


# ============ users profile update =========================
class SuccessBase(BaseModel):
    message: str

    class Config:
        from_attributes = True


class PhoneNumberBase(BaseModel):
    phone_number: str

    class Config:
        from_attributes = True


class TwitterBase(BaseModel):
    twitter: str

    class Config:
        from_attributes = True


class FacebookBase(BaseModel):
    facebook: str

    class Config:
        from_attributes = True


class LinkedinBase(BaseModel):
    linkedin: str

    class Config:
        from_attributes = True


class ProfilePicture(BaseModel):
    profile_picture_name: str

    class Config:
        from_attributes = True


class ProfileUpdateBase(BaseModel):
    phone_number: str
    twitter: str
    facebook: str
    linkedin: str

    class Config:
        from_attributes = True


class NewsletterSubscription(BaseModel):
    email: EmailStr

    class Config:
        from_attributes = True


class NewsletterSubscriptionResp(BaseModel):
    email: EmailStr
    date_subscribed: datetime

    class Config:
        from_attributes = True


# ============ Daraja API=========================
class StkPushBase(BaseModel):
    amount: int
    phone_number: str
    transaction_destination: str
    transaction_code: str
    description: str

    class Config:
        from_attributes = True


class StkPushStatusBase(BaseModel):
    checkout_request_id: str
    unprocessed_transaction_code: str
    phone_number: str
    destination_wallet: str
    amount: int

    class Config:
        from_attributes = True


class SendMoneyBase(BaseModel):
    amount: int
    phone_number: str
    description: str
    originator_conversation_id: str

    class Config:
        from_attributes = True


class CallbackDataBase(BaseModel):
    MerchantRequestID: str
    CheckoutRequestID: str
    ResultCode: int
    ResultDesc: str
    Amount: int
    MpesaReceiptNumber: str
    TransactionDate: datetime
    PhoneNumber: str

    class Config:
        from_attributes = True


class MpesaResponse(BaseModel):
    MerchantRequestID: str = Field(..., alias="MerchantRequestID")
    CheckoutRequestID: str = Field(..., alias="CheckoutRequestID")
    ResultCode: int = Field(..., alias="ResultCode")
    ResultDesc: str = Field(..., alias="ResultDesc")
    Amount: float = Field(..., alias="Amount")
    MpesaReceiptNumber: str = Field(..., alias="MpesaReceiptNumber")
    TransactionDate: int = Field(..., alias="TransactionDate")
    PhoneNumber: int = Field(..., alias="PhoneNumber")


class B2CMpesaResponse(BaseModel):
    ResultType: int
    ResultCode: int
    ResultDesc: str
    OriginatorConversationID: str
    ConversationID: str
    TransactionID: str
    ResultParameters: dict
    ReferenceData: dict


# ============ Mpesa B2C RESULT =========================
class ResultParameter(BaseModel):
    Key: str
    Value: str


class ResultParameters(BaseModel):
    ResultParameter: List[ResultParameter]


class ReferenceItem(BaseModel):
    Key: str
    Value: str


class ReferenceData(BaseModel):
    ReferenceItem: ReferenceItem


class Result(BaseModel):
    ResultType: int
    ResultCode: int
    ResultDesc: str
    OriginatorConversationID: str
    ConversationID: str
    TransactionID: str
    ResultParameters: ResultParameters
    ReferenceData: ReferenceData


class B2CMpesaResult(BaseModel):
    Result: Result


# =========== fine ==============
class MemberFineBase(BaseModel):
    member_id: int
    chama_id: int
    amount: int

    class Config:
        from_attributes = True


class MemberMpesaFineBase(BaseModel):
    transaction_code: str
    phone_number: str
    member_id: int
    chama_id: int
    amount: int

    class Config:
        from_attributes = True


class MemberFineResp(BaseModel):
    balance_after_fines: int

    class Config:
        from_attributes = True


class MemberFines(BaseModel):
    member_id: int
    chama_id: int

    class Config:
        from_attributes = True


class MemberFinesResp(BaseModel):
    has_fines: bool

    class Config:
        from_attributes = True


class MpesaPayFinesBase(BaseModel):
    amount: int
    transaction_destination: int
    phone_number: str
    transaction_code: str
    member_id: int

    class Config:
        from_attributes = True


class TotalFinesResp(BaseModel):
    total_fines: int

    class Config:
        from_attributes = True


# =========== chama setings =================
class AutoContributeBase(BaseModel):
    member_id: int
    chama_id: int
    expected_amount: int
    next_contribution_date: datetime
    status: str

    class Config:
        from_attributes = True


class TransferWalletBase(BaseModel):
    amount: int
    destination_wallet: str

    class Config:
        from_attributes = True


# share increase setting
class merryGoRoundShareIncrease(BaseModel):
    max_no_shares: int
    deadline_date: str
    adjustment_fee: int

    class Config:
        from_attributes = True

class merryGoRoundShareIncreaseReq(BaseModel):
    new_shares: int

    class Config:
        from_attributes = True

class newChamaMembers(BaseModel):
    late_joining_fee: int
    deadline: str

    class Config:
        from_attributes = True

# Tbale banking
class TableBankingRateBase(BaseModel):
    interest_rate: float

    class Config:
        from_attributes = True

class TableBankingRequestLoan(BaseModel):
    requested_amount: int
    contribution_day_is_today: bool

    class Config:
        from_attributes = True

class TableBankingPayLoan(BaseModel):
    amount: int

    class Config:
        from_attributes = True