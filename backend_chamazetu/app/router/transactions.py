from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List
from zoneinfo import ZoneInfo
import logging


from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/transactions", tags=["transactions"])

nairobi_tz = ZoneInfo("Africa/Nairobi")

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")


# create deposit transaction for a logged in member to chama
@router.post(
    "/direct_deposit",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.TransactionResp,
)
async def create_deposit_transaction(
    transaction: schemas.DirectTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        with db.begin():
            transaction_dict = transaction.dict()
            transaction_dict["transaction_type"] = "deposit"
            transaction_dict["member_id"] = transaction.member_id
            transaction_dict["transaction_completed"] = True
            transaction_dict["date_of_transaction"] = datetime.now(nairobi_tz).replace(
                tzinfo=None
            )
            transaction_dict["updated_at"] = datetime.now(nairobi_tz).replace(
                tzinfo=None
            )
            transaction_dict["transaction_code"] = transaction.transaction_code

            new_transaction = models.Transaction(**transaction_dict)
            db.add(new_transaction)
            db.flush()  # flush to get the id of the transaction and trigger constraints
            db.refresh(new_transaction)

        return new_transaction

    except Exception as e:
        print("------direct deposit error--------")
        transaction_error_logger.error(f"Failed to create transaction: {e}")
        raise HTTPException(status_code=400, detail="Failed to create transaction")


@router.post(
    "/before_processing_direct_deposit",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.TransactionResp,
)
async def create_unprocessed_deposit_transaction(
    transaction: schemas.BeforeProcessingBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        print("===========before processing ===========")
        with db.begin():
            transaction_dict = transaction.dict()
            transaction_dict["transaction_type"] = transaction.transaction_type
            transaction_dict["member_id"] = transaction.member_id
            transaction_dict["transaction_completed"] = False
            transaction_dict["date_of_transaction"] = datetime.now(nairobi_tz).replace(
                tzinfo=None
            )
            transaction_dict["updated_at"] = datetime.now(nairobi_tz).replace(
                tzinfo=None
            )
            transaction_dict["transaction_code"] = transaction.transaction_code

            new_transaction = models.Transaction(**transaction_dict)
            db.add(new_transaction)
            db.flush()  # flush to get the id of the transaction and trigger constraints
            db.refresh(new_transaction)

        return new_transaction

    except Exception as e:
        print("------direct deposit error--------")
        transaction_error_logger.error(f"Failed to create unprocessed transaction: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to create unprocessed transaction"
        )


# create a deposit transaction from wallet to chama
@router.post(
    "/deposit_from_wallet",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.WalletTransactionResp,
)
async def create_deposit_transaction_from_wallet(
    wallet_transaction: schemas.WalletTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):

    try:
        wallet_transaction_dict = wallet_transaction.dict()
        wallet_transaction_dict["transaction_type"] = "moved_to_chama"
        wallet_transaction_dict["member_id"] = current_user.id
        wallet_transaction_dict["transaction_completed"] = True
        wallet_transaction_dict["transaction_date"] = datetime.now(nairobi_tz).replace(
            tzinfo=None
        )
        wallet_transaction_dict["transaction_code"] = uuid4().hex

        new_wallet_transaction = models.Wallet_Transaction(**wallet_transaction_dict)
        db.add(new_wallet_transaction)
        db.commit()
        db.refresh(new_wallet_transaction)

        # add record to transactions table
        transaction_dict = {
            "amount": new_wallet_transaction.amount,
            "phone_number": generateWalletNumber(current_user.id),
            "chama_id": wallet_transaction.transaction_destination,
            "transaction_type": "deposit",
            "transaction_origin": "wallet_deposit",
            "member_id": current_user.id,
            "transaction_completed": True,
            "date_of_transaction": new_wallet_transaction.transaction_date,
            "updated_at": new_wallet_transaction.transaction_date,
            "transaction_code": new_wallet_transaction.transaction_code,
        }

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()

        return new_wallet_transaction

    except Exception as e:
        print("------deposit from wallet error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# TODO: above to support fines
# ============duplicate of the above to repay fines================
@router.post(
    "/record_fine_payment",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.WalletTransactionResp,
)
async def create_fine_repayment_transaction_from_wallet(
    wallet_transaction: schemas.WalletTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):

    try:
        print("===========record fine wallet transaction===========")
        wallet_transaction_dict = wallet_transaction.dict()
        wallet_transaction_dict["transaction_type"] = "moved_to_chama"
        wallet_transaction_dict["member_id"] = current_user.id
        wallet_transaction_dict["transaction_completed"] = True
        wallet_transaction_dict["transaction_date"] = datetime.now(nairobi_tz).replace(
            tzinfo=None
        )
        wallet_transaction_dict["transaction_code"] = uuid4().hex

        new_wallet_transaction = models.Wallet_Transaction(**wallet_transaction_dict)
        db.add(new_wallet_transaction)
        db.commit()
        db.refresh(new_wallet_transaction)

        # add record to transactions table
        transaction_dict = {
            "amount": new_wallet_transaction.amount,
            "phone_number": generateWalletNumber(current_user.id),
            "chama_id": wallet_transaction.transaction_destination,
            "transaction_type": "fine deduction",
            "transaction_origin": "wallet_deposit",
            "member_id": current_user.id,
            "transaction_completed": True,
            "date_of_transaction": new_wallet_transaction.transaction_date,
            "updated_at": new_wallet_transaction.transaction_date,
            "transaction_code": new_wallet_transaction.transaction_code,
        }

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()

        return new_wallet_transaction

    except Exception as e:
        print("------deposit from wallet error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# =========================mpesa fine repayment recording=========
@router.post(
    "/record_fine_payment_from_mpesa",
    status_code=status.HTTP_201_CREATED,
)
async def create_fine_repayment_transaction_from_mpesa(
    mpesa_transaction: schemas.MpesaPayFinesBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        print("===========record fine mpesa transaction===========")

        # add record to transactions table
        transaction_dict = {
            "amount": mpesa_transaction.amount,
            "phone_number": mpesa_transaction.phone_number,
            "chama_id": mpesa_transaction.transaction_destination,
            "transaction_type": "fine deduction",
            "transaction_origin": "direct_deposit",
            "member_id": mpesa_transaction.member_id,
            "transaction_completed": True,
            "date_of_transaction": datetime.now(nairobi_tz).replace(tzinfo=None),
            "updated_at": datetime.now(nairobi_tz),
            "transaction_code": mpesa_transaction.transaction_code,
        }

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()

        return

    except Exception as e:
        print("------deposit from mpesa error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# ================================================================


def generateWalletNumber(member_id):
    prefix = "94" + str(member_id)
    wallet_number = prefix.zfill(12)
    return wallet_number


# combining multiple transactions into one - wallet update, account update and direct deposit
@router.post("/unified_deposit_transactions", status_code=status.HTTP_201_CREATED)
async def unified_deposit_transactions(
    transactions: schemas.UnifiedTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        if not transactions.wallet_deposit:
            # prepare wallet transaction
            wallet_transaction = transactions.wallet_update
            if wallet_transaction:
                wallet_dict = wallet_transaction.dict()
                wallet_dict["transaction_date"] = datetime.now(nairobi_tz).replace(
                    tzinfo=None
                )
                wallet_dict["transaction_completed"] = True
                wallet_dict["transaction_destination"] = 0
                wallet_dict["transaction_code"] = transactions.transaction_code
                wallet_dict["member_id"] = transactions.member_id

                new_wallet_transaction = models.Wallet_Transaction(**wallet_dict)
                db.add(new_wallet_transaction)

                # update the member wallet balance
                member = (
                    db.query(models.Member)
                    .filter(models.Member.id == transactions.member_id)
                    .first()
                )
                if not member:
                    raise HTTPException(status_code=404, detail="Member not found")
                member.wallet_balance += wallet_transaction.amount

            # prepare direct deposit transaction
            direct_deposit = transactions.direct_deposit
            if direct_deposit:
                direct_dict = direct_deposit.dict()
                direct_dict["transaction_type"] = "deposit"
                direct_dict["member_id"] = transactions.member_id
                direct_dict["transaction_completed"] = True
                direct_dict["transaction_code"] = transactions.transaction_code
                direct_dict["date_of_transaction"] = datetime.now(nairobi_tz).replace(
                    tzinfo=None
                )
                direct_dict["updated_at"] = direct_dict["date_of_transaction"]
                direct_dict["chama_id"] = transactions.chama_id

                new_direct_deposit = models.Transaction(**direct_dict)
                db.add(new_direct_deposit)

                # update the chama account with direct deposit amount
                chama_account = (
                    db.query(models.Chama_Account)
                    .filter(models.Chama_Account.chama_id == transactions.chama_id)
                    .first()
                )
                if not chama_account:
                    raise HTTPException(
                        status_code=404, detail="Chama account not found"
                    )
                chama_account.account_balance += direct_deposit.amount
        else:
            # prepare wallet transaction - all cont are made so we only have to move money to the wallet
            wallet_transaction = transactions.wallet_deposit
            if wallet_transaction:
                wallet_dict = wallet_transaction.dict()
                wallet_dict["transaction_date"] = datetime.now(nairobi_tz).replace(
                    tzinfo=None
                )
                wallet_dict["transaction_completed"] = True
                wallet_dict["transaction_destination"] = 0
                wallet_dict["transaction_code"] = transactions.transaction_code
                wallet_dict["member_id"] = transactions.member_id

                new_wallet_deposit = models.Wallet_Transaction(**wallet_dict)
                db.add(new_wallet_deposit)

                # update the member wallet balance
                member = (
                    db.query(models.Member)
                    .filter(models.Member.id == transactions.member_id)
                    .first()
                )
                if not member:
                    raise HTTPException(status_code=404, detail="Member not found")
                member.wallet_balance += wallet_transaction.amount

        # prepare unprocessed transaction
        unprocessed_transaction = (
            db.query(models.Transaction)
            .filter(
                and_(
                    models.Transaction.member_id == transactions.member_id,
                    models.Transaction.chama_id == transactions.chama_id,
                    models.Transaction.transaction_origin == "mpesa",
                    models.Transaction.transaction_type == "unprocessed deposit",
                    models.Transaction.transaction_code
                    == transactions.transaction_code,
                    models.Transaction.transaction_completed == False,
                )
            )
            .first()
        )
        if not unprocessed_transaction:
            raise HTTPException(
                status_code=404, detail="Unprocessed transaction not found"
            )
        unprocessed_transaction.transaction_completed = True
        unprocessed_transaction.updated_at = datetime.now(nairobi_tz).replace(
            tzinfo=None
        )
        unprocessed_transaction.transaction_type = "processed"

        db.commit()
        return {"message": "Unified transactions created successfully"}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(
            f"Failed to create unified transaction: {e} at {datetime.now(nairobi_tz)}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to create unified transaction"
        )


# fetch transactions for a certain chama
@router.get(
    "/recent/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.RecentTransactionResp],
)
async def get_transactions(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        transactions = (
            db.query(models.Transaction)
            .filter(
                and_(
                    models.Transaction.chama_id == chama_id,
                    models.Transaction.transaction_completed == True,
                    models.Transaction.transaction_origin != "mpesa",
                )
            )
            .order_by(desc(models.Transaction.date_of_transaction))
            .limit(3)
            .all()
        )

        return [
            schemas.RecentTransactionResp(**transaction.__dict__)
            for transaction in transactions
        ]
    except Exception as e:
        print("------chamaname chama error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to fetch transactions")


# fetch transaction for all members in a chama, members ids are passed in the request body as a list
@router.get("/{chamaname}/members", status_code=status.HTTP_200_OK)
async def get_transactions_for_members(
    chama_data: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        chama_id = chama_data["chama_id"]
        transactions = (
            db.query(models.Transaction)
            .filter(models.Transaction.chama_id == chama_id)
            .all()
        )
        members = chama_data["members_ids"]
        members_transactions = {}
        for member in members:
            member_transactions = []
            for transaction in transactions:
                if (
                    transaction.member_id == member
                    and (transaction.date_of_transaction).strftime("%Y-%m-%d")
                    >= chama_data["date_of_transaction"]
                ):
                    member_transactions.append(transaction)
            members_transactions[member] = member_transactions

        return members_transactions

    except Exception as e:
        print("------extracting members transactions failed--------")
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to fetch members transactions"
        )


# above route optimized
@router.get("/members/{chama_id}", status_code=status.HTTP_200_OK)
async def get_transactions_for_members(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    try:
        date_of_transaction = (
            get_sunday_date().date()
        )  # Assuming get_sunday_date() returns a datetime object

        # Optimized query to fetch transactions for all members after the specified date
        transactions = (
            db.query(models.Transaction)
            .filter(
                models.Transaction.chama_id == chama_id,
                models.Transaction.transaction_completed == True,
                models.Transaction.transaction_origin != "mpesa",
                func.date(models.Transaction.date_of_transaction)
                >= date_of_transaction,
            )
            .all()
        )

        # Organizing transactions by member_id
        members_transactions = {}
        for transaction in transactions:
            if transaction.member_id not in members_transactions:
                members_transactions[transaction.member_id] = []
            members_transactions[transaction.member_id].append(transaction)

        return members_transactions

    except Exception as e:
        print("------extracting members transactions failed--------")
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to fetch members transactions"
        )


def get_sunday_date():
    timezone = ZoneInfo("Africa/Nairobi")
    today = datetime.now(timezone)
    # calculating the number of days to subtract to get the first day of the week
    days_to_subtract = (today.weekday() + 1) % 7
    # subtracting the days to get the first day of the week
    sunday_date = today - timedelta(days=days_to_subtract)
    sunday_date = sunday_date.replace(hour=0, minute=0, second=0, microsecond=0)
    print("------sunday date--------")
    print(sunday_date)
    return sunday_date
