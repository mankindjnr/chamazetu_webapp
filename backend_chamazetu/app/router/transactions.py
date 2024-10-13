from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List
from zoneinfo import ZoneInfo
import logging


from .. import schemas, database, utils, oauth2, models
from .members import generateWalletNumber, generate_transaction_code

router = APIRouter(prefix="/transactions", tags=["transactions"])

nairobi_tz = ZoneInfo("Africa/Nairobi")

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")


# record a pending deposit transaction from mpesa
@router.post(
    "/unprocessed_deposit",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UnprocessedWalletDepositResp,
)
async def create_unprocessed_deposit_transaction(
    transaction: schemas.UnprocessedWalletDepositBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        user = (
            db.query(models.User).filter(models.User.id == transaction.user_id).first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # retrieve the last 12 characters of transaction destnation
        if transaction.transaction_destination[-12:] == "Registration":
            chama_id = int(transaction.transaction_destination[:-12])
            today = datetime.now(nairobi_tz).date()
            # check if the today is passed the last joinig date
            chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
            if not chama:
                raise HTTPException(status_code=404, detail="Chama not found")

            if chama.last_joining_date < today:
                raise HTTPException(
                    status_code=400, detail="Chama registration period has ended"
                )

        transaction_code = generate_transaction_code(
            transaction.transaction_type, transaction.transaction_destination
        )
        unprocessed_transaction = {
            "user_id": transaction.user_id,
            "amount": transaction.amount,
            "origin": transaction.transaction_origin,
            "destination": transaction.transaction_destination,
            "transaction_type": transaction.transaction_type,
            "transaction_date": datetime.now(nairobi_tz).replace(
                tzinfo=None, microsecond=0
            ),
            "transaction_completed": False,
            "transaction_code": transaction_code,
        }

        new_transaction = models.WalletTransaction(**unprocessed_transaction)
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        return {"transaction_code": transaction_code}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        transaction_error_logger.error(f"Failed to create unprocessed transaction: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to create unprocessed transaction"
        )


# use phone_number and amount to see if an unprocessed transaction exists
@router.get(
    "/unprocessed_deposit/{phone_number}/{amount}",
    status_code=status.HTTP_200_OK,
)
async def check_unprocessed_deposit_transaction(
    phone_number: str,
    amount: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        user = db.query(models.User).filter(models.User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # we will also check if the transaction has happened atleast 5 minutes ago
        five_minutes_ago = datetime.now(nairobi_tz) - timedelta(minutes=5)

        unprocessed_transaction = (
            db.query(models.WalletTransaction)
            .filter(
                and_(
                    models.WalletTransaction.user_id == current_user.id,
                    models.WalletTransaction.origin == phone_number,
                    models.WalletTransaction.destination == user.wallet_id,
                    models.WalletTransaction.amount == amount,
                    models.WalletTransaction.transaction_completed == False,
                    models.WalletTransaction.transaction_date <= five_minutes_ago,
                    models.WalletTransaction.transaction_type
                    == "unprocessed wallet deposit",
                )
            )
            .first()
        )

        if not unprocessed_transaction:
            return {"unprocessed_transaction_exists": False}

        return {
            "unprocessed_transaction_exists": True,
            "transaction_code": unprocessed_transaction.transaction_code,
        }
    except Exception as e:
        transaction_error_logger.error(f"Failed to check unprocessed transaction: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to check unprocessed transaction"
        )


# create an unprocessed withdrawal transaction
@router.post(
    "/unprocessed_wallet_withdrawal",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UnprocessedWalletWithdrawalResp,
)
async def create_unprocessed_withdrawal_transaction(
    transaction: schemas.UnprocessedWalletWithdrawalBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        user = db.query(models.User).filter(models.User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        transaction_code = generate_transaction_code(
            "unprocessed wallet withdrawal", transaction.transaction_destination
        )
        unprocessed_transaction = {
            "user_id": current_user.id,
            "amount": transaction.amount,
            "origin": user.wallet_id,
            "destination": transaction.transaction_destination,
            "transaction_type": "unprocessed wallet withdrawal",
            "transaction_date": datetime.now(nairobi_tz).replace(
                tzinfo=None, microsecond=0
            ),
            "transaction_completed": False,
            "transaction_code": transaction_code,
        }

        new_transaction = models.WalletTransaction(**unprocessed_transaction)
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        return {"transaction_code": transaction_code}
    except Exception as e:
        transaction_error_logger.error(f"Failed to create unprocessed transaction: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to create unprocessed transaction"
        )


@router.put(
    "/process_unprocessed_withdrawal",
    status_code=status.HTTP_200_OK,
)
async def process_unprocessed_withdrawal_transaction(
    transaction: schemas.ProcessUnprocessedWalletWithdrawalBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        user = db.query(models.User).filter(models.User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        unprocessed_transaction = (
            db.query(models.WalletTransaction)
            .filter(
                and_(
                    models.WalletTransaction.user_id == current_user.id,
                    models.WalletTransaction.transaction_code
                    == transaction.unprocessed_transaction_code,
                    models.WalletTransaction.amount == transaction.amount,
                    models.WalletTransaction.transaction_completed == False,
                )
            )
            .first()
        )
        if not unprocessed_transaction:
            raise HTTPException(
                status_code=404, detail="Unprocessed transaction not found"
            )

        # update the wallet balance
        user.wallet_balance -= transaction.amount

        # update the unprocessed transaction
        unprocessed_transaction.transaction_completed = True
        unprocessed_transaction.transaction_code = transaction.mpesa_receipt_number
        unprocessed_transaction.transaction_date = datetime.now(nairobi_tz).replace(
            tzinfo=None, microsecond=0
        )
        unprocessed_transaction.transaction_type = "processed"

        db.commit()
        return {"message": "Transaction processed successfully"}
    except Exception as e:
        transaction_error_logger.error(
            f"Failed to process unprocessed transaction: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to process unprocessed transaction"
        )


# update the wallet balance after a successful mpesa transaction and update the unprocessed transaction
@router.put(
    "/load_wallet",
    status_code=status.HTTP_200_OK,
    response_model=schemas.LoadWalletResp,
)
async def load_wallet(
    deposit: schemas.LoadWalletBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        with db.begin():
            user = (
                db.query(models.User)
                .filter(models.User.id == deposit.user_id)
                .with_for_update()
                .first()
            )
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            unprocessed_transaction = (
                db.query(models.WalletTransaction)
                .filter(
                    and_(
                        models.WalletTransaction.user_id == deposit.user_id,
                        models.WalletTransaction.transaction_code
                        == deposit.unprocessed_code,
                        models.WalletTransaction.amount == deposit.amount,
                        models.WalletTransaction.transaction_completed == False,
                    )
                )
                .with_for_update()
                .first()
            )
            if not unprocessed_transaction:
                raise HTTPException(
                    status_code=404, detail="Unprocessed transaction not found"
                )

            transaction_date = datetime.now(nairobi_tz).replace(
                tzinfo=None, microsecond=0
            )
            new_wallet_transaction = models.WalletTransaction(
                amount=deposit.amount,
                transaction_type="deposit",
                origin=deposit.transaction_origin,
                destination=deposit.wallet_id,
                user_id=deposit.user_id,
                transaction_completed=True,
                transaction_date=transaction_date,
                transaction_code=deposit.transaction_code,
            )

            db.add(new_wallet_transaction)

            # update the wallet balance
            user.wallet_balance += deposit.amount

            # update the unprocessed transaction
            unprocessed_transaction.transaction_completed = True
            unprocessed_transaction.transaction_date = transaction_date
            unprocessed_transaction.transaction_type = "processed"

            db.commit()

        return {"amount": deposit.amount, "transaction_code": deposit.transaction_code}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to load wallet: {e}")
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# transfer from one user wallet to anoher
@router.post("/transfer", status_code=status.HTTP_201_CREATED)
async def transfer_wallet(
    transfer: schemas.TransferWalletBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        user = db.query(models.User).filter(models.User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # check if the user has enough balance to transfer
        if user.wallet_balance < transfer.amount:
            raise HTTPException(
                status_code=400, detail="Insufficient balance to transfer"
            )

        # check if the destination wallet exists
        destination_user = (
            db.query(models.User)
            .filter(models.User.wallet_id == transfer.destination_wallet)
            .first()
        )
        if not destination_user:
            raise HTTPException(status_code=404, detail="Recipient wallet not found")

        if user.id == destination_user.id:
            raise HTTPException(
                status_code=400, detail="Cannot transfer to the same wallet"
            )

        transaction_code = generate_transaction_code(
            "transfer", transfer.destination_wallet
        )
        transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)

        new_transaction = models.WalletTransaction(
            amount=transfer.amount,
            transaction_type="transfer",
            origin=user.wallet_id,
            destination=transfer.destination_wallet,
            user_id=user.id,
            transaction_completed=True,
            transaction_date=transaction_date,
            transaction_code=transaction_code,
        )

        db.add(new_transaction)

        # update the wallet balance
        user.wallet_balance -= transfer.amount
        destination_user.wallet_balance += transfer.amount

        db.commit()

        return {"transfer": "successful"}
    except HTTPException as http_exc:
        # no need for rollback since its a logical error, not a database error
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to transfer wallet: {e}")
        raise HTTPException(status_code=400, detail="Failed to transfer wallet")


# =========================mpesa fine repayment recording=========
# ================================================================


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
