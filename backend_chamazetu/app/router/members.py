from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy import func, update, and_, table, column, desc
from sqlalchemy.orm import Session, joinedload, aliased
from typing import Union
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import logging, random, time
from typing import List
from uuid import uuid4

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/members", tags=["members"])

nairobi_tz = ZoneInfo("Africa/Nairobi")

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")


# member dashboard
@router.get("/dashboard", status_code=status.HTTP_200_OK)
async def member_dashboard(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        member = db.query(models.User).filter(models.User.id == current_user.id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        member_recent_transactions = (
            db.query(
                models.Activity.activity_title,
                models.Activity.activity_type,
                models.ActivityTransaction.amount,
                models.ActivityTransaction.transaction_type,
                models.ActivityTransaction.transaction_date,
            )
            .join(
                models.ActivityTransaction,
                models.Activity.id == models.ActivityTransaction.activity_id,
            )
            .filter(
                and_(
                    models.ActivityTransaction.user_id == current_user.id,
                    models.ActivityTransaction.transaction_completed == True,
                )
            )
            .order_by(desc(models.ActivityTransaction.transaction_date))
            .limit(3)
        )

        wallet_transactions = (
            db.query(models.WalletTransaction)
            .filter(
                and_(
                    models.WalletTransaction.user_id == current_user.id,
                    models.WalletTransaction.transaction_completed == True,
                    models.WalletTransaction.transaction_type == "deposit",
                )
            )
            .order_by(desc(models.WalletTransaction.transaction_date))
            .limit(3)
            .all()
        )

        # sent transactions will be from the B2CResults table and will be filtered through the transactionreceipt and transaction_code from wallet_transactions
        # so we will use two tables

        sent_transactions = (
            db.query(
                models.B2CResults.transactionreceipt,
                models.B2CResults.transactionid,
                models.B2CResults.transactioncompleteddatetime,
                models.B2CResults.transactionamount,
                models.B2CResults.receiverpartypublicname,
            )
            .filter(
                and_(
                    models.B2CResults.transactionreceipt
                    == models.WalletTransaction.transaction_code,
                    models.WalletTransaction.user_id == current_user.id,
                )
            )
            .order_by(desc(models.B2CResults.transactioncompleteddatetime))
            .limit(3)
            .all()
        )

        member_chamas = (
            db.query(models.Chama)
            .join(
                models.chama_user_association,
                models.Chama.id == models.chama_user_association.c.chama_id,
            )
            .filter(models.chama_user_association.c.user_id == current_user.id)
            .all()
        )

        user_profile = (
            db.query(models.User.profile_picture)
            .filter(models.User.id == current_user.id)
            .scalar()
        )

        member_chamas_data = [
            {
                "chama_id": chama.id,
                "chama_name": chama.chama_name,
                "category": chama.category,
            }
            for chama in member_chamas
        ]

        recent_transactions = [
            {
                "activity_title": transaction.activity_title,
                "activity_type": transaction.activity_type,
                "transaction_amount": transaction.amount,
                "transaction_type": transaction.transaction_type,
                "transaction_date": transaction.transaction_date.strftime("%d-%B-%Y"),
                "transaction_time": transaction.transaction_date.strftime("%H:%M:%S"),
            }
            for transaction in member_recent_transactions
        ]

        wallet_transactions_data = [
            {
                "transaction_type": transaction.transaction_type,
                "transaction_date": transaction.transaction_date.strftime("%d-%B-%Y"),
                "transaction_time": transaction.transaction_date.strftime("%H:%M:%S"),
                "transaction_amount": transaction.amount,
            }
            for transaction in wallet_transactions
        ]

        # receiverpartypublicname = 254720090889 - AMOS NJOROGE KAIRU

        sent_transactions_data = [
            {
                "transaction_receipt": transaction.transactionreceipt,
                "transaction_id": transaction.transactionid,
                "transaction_date": transaction.transactioncompleteddatetime.strftime(
                    "%d-%B-%Y"
                ),
                "transaction_time": transaction.transactioncompleteddatetime.strftime(
                    "%H:%M:%S"
                ),
                "transaction_amount": transaction.transactionamount,
                "receiver_phone": (transaction.receiverpartypublicname).split("-")[0],
                "receiver_name": (transaction.receiverpartypublicname).split("-")[1],
            }
            for transaction in sent_transactions
        ]

        return {
            "wallet_balance": member.wallet_balance,
            "zetucoins": member.zetucoins,
            "recent_transactions": recent_transactions,
            "wallet_transactions": wallet_transactions_data,
            "sent_transactions": sent_transactions_data,
            "member_chamas": member_chamas_data,
            "profile_picture": user_profile,
        }

    except Exception as e:
        transaction_error_logger.error(f"Failed to get member dashboard {e}")
        raise HTTPException(status_code=400, detail="Failed to get member dashboard")


# get a members chama dashboard
@router.get("/chama_dashboard/{chama_id}", status_code=status.HTTP_200_OK)
async def chama_dashboard(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()

        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        a_chama_member = (
            db.query(models.chama_user_association)
            .filter(
                and_(
                    models.chama_user_association.c.chama_id == chama_id,
                    models.chama_user_association.c.user_id == current_user.id,
                )
            )
            .first()
        )

        print("=======", a_chama_member)
        if not a_chama_member:
            raise HTTPException(status_code=404, detail="Member not in chama")

        # for readbaility
        ActivityContribution = aliased(models.ActivityContributionDate)
        ActivityUserAssoc = aliased(models.activity_user_association)

        chama_activities = (
            db.query(
                ActivityContribution.next_contribution_date,
                ActivityContribution.activity_title,
                ActivityContribution.activity_type,
                ActivityUserAssoc.c.activity_id,
            )
            .join(
                ActivityUserAssoc,
                ActivityContribution.activity_id == ActivityUserAssoc.c.activity_id,
            )
            .filter(
                and_(
                    ActivityContribution.chama_id == chama_id,
                    ActivityUserAssoc.c.user_id == current_user.id,
                )
            )
            .order_by(desc(ActivityContribution.next_contribution_date))
            .all()
        )
        print("====chama activities====")

        user_wallet_balance = (
            db.query(models.User.wallet_balance)
            .filter(models.User.id == current_user.id)
            .scalar()
        )
        print("====user wallet balance====")

        if not user_wallet_balance:
            user_wallet_balance = 0.0
        print(user_wallet_balance)

        chama_total_fines = (
            db.query(func.coalesce(func.sum(models.ActivityFine.expected_repayment), 0))
            .filter(models.ActivityFine.chama_id == chama_id)
            .filter(models.ActivityFine.user_id == current_user.id)
            .filter(models.ActivityFine.is_paid == False)
            .scalar()
        )
        print("====chama total fines====")

        # have a table to track the total fines paid instead of calculating it every time
        chama_account = (
            db.query(models.Chama_Account)
            .filter(models.Chama_Account.chama_id == chama_id)
            .first()
        )
        activities_data = [
            {
                "contribution_date": activity.next_contribution_date.strftime(
                    "%d-%B-%Y"
                ),
                "title": activity.activity_title,
                "type": activity.activity_type,
                "activity_id": activity.activity_id,
            }
            for activity in chama_activities
        ]
        print("====chama activities====")
        print(activities_data)

        return {
            "chama_name": chama.chama_name,
            "chama_id": chama.id,
            "chama_activities": activities_data,
            "wallet_balance": user_wallet_balance,
            "total_fines": chama_total_fines,
            "account_balance": chama_account.account_balance,
            "available_balance": chama_account.available_balance,
        }
    except HTTPException as e:
        transaction_error_logger.error(f"Failed to get chama dashboard {e}")
        raise
    except Exception as e:
        transaction_error_logger.error(f"Failed to get chama dashboard {e}")
        raise HTTPException(status_code=400, detail="Failed to get chama dashboard")


# get all chamas a member is connected to using member id
@router.get(
    "/chamas",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.MemberChamasResp],
)
async def get_member_chamas(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):

    try:
        print("=====getting member chamas=====")
        print(current_user.id)
        member_chamas = (
            db.query(models.Chama)
            .join(
                models.chama_user_association,
                models.Chama.id == models.chama_user_association.c.chama_id,
            )
            .filter(models.chama_user_association.c.user_id == current_user.id)
            .all()
        )
        transaction_info_logger.info("Member chamas retrieved")
        transaction_info_logger.info(member_chamas)

        return [schemas.MemberChamasResp.from_orm(chama) for chama in member_chamas]

    except Exception as e:
        transaction_error_logger.error(f"Failed to get member chamas {e}")
        raise HTTPException(status_code=400, detail="Failed to get member chamas")


# get members number of shares in a certain chama
@router.get(
    "/expected_contribution/{user_id}/{activity_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberSharesResp,
)
async def get_member_shares(
    user_id: int,
    activity_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        user_shares = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.user_id == user_id,
                    models.activity_user_association.c.activity_id == activity_id,
                )
            )
            .first()
        )

        if not user_shares:
            raise HTTPException(status_code=404, detail="user shares not found")

        expected_contribution = user_shares.shares * activity.activity_amount

        return {"expected_contribution": expected_contribution}

    except Exception as e:
        transaction_error_logger.error(f"Failed to get member shares {e}")
        raise HTTPException(
            status_code=400, detail="Failed to get members expected contribution amount"
        )


# what a member has contributed to a chama from previous chama day to the next chama day
@router.get(
    "/contribution_so_far/{user_id}/{activity_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberContributionResp,
)
async def get_member_contribution_so_far(
    user_id: int,
    activity_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        contribution_dates = (
            db.query(models.ActivityContributionDate)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .first()
        )
        prev_contribution_date = contribution_dates.previous_contribution_date.date()
        next_contribution_date = contribution_dates.next_contribution_date.date()

        # rewrite the above query to sum the amount using coalesce
        total_contributions = (
            db.query(func.coalesce(func.sum(models.ActivityTransaction.amount), 0))
            .filter(
                and_(
                    models.ActivityTransaction.user_id == user_id,
                    models.ActivityTransaction.activity_id == activity_id,
                    models.ActivityTransaction.transaction_completed == True,
                    models.ActivityTransaction.transaction_type == "contribution",
                    models.ActivityTransaction.is_reversed == False,
                    func.date(models.ActivityTransaction.transaction_date)
                    > prev_contribution_date,
                    func.date(models.ActivityTransaction.transaction_date)
                    <= next_contribution_date,
                )
            )
            .scalar()
        )

        return {"total_contribution": total_contributions}
    except Exception as e:
        transaction_error_logger.error(f"Failed to get member contribution so far {e}")
        raise HTTPException(
            status_code=400, detail="Failed to get members contribution so far"
        )


# make a contribution to the merry_go_round activity should unified contribution, pays fines and contributes to remaining expected amount
@router.post(
    "/contribute/merry-go-round/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def contribute_to_merry_go_round(
    activity_id: int,
    contrib_data: schemas.ContributeToActivityBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        expected_amount = contrib_data.expected_contribution
        amount = contrib_data.amount
        transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        wallet_id = (
            db.query(models.User.wallet_id)
            .filter(models.User.id == current_user.id)
            .scalar()
        )

        fines = (
            db.query(models.ActivityFine)
            .filter(
                and_(
                    models.ActivityFine.activity_id == activity_id,
                    models.ActivityFine.user_id == current_user.id,
                    models.ActivityFine.is_paid == False,
                )
            )
            .order_by(models.ActivityFine.fine_date)
            .with_for_update()  # lock the rows for update
            .all()
        )

        total_fines_repaid = 0
        amount_contributed = 0

        with db.begin_nested():
            if fines:
                for fine in fines:
                    fine_transaction_code = generate_transaction_code(
                        "manual_fine_repayment", wallet_id
                    )

                    if amount >= fine.expected_repayment:
                        amount -= fine.expected_repayment
                        fine_amount_repaid = fine.expected_repayment
                        fine.is_paid = True
                        fine.paid_date = transaction_date
                        fine.expected_repayment = 0
                    else:
                        fine.expected_repayment -= amount
                        fine_amount_repaid = amount
                        amount = 0

                    total_fines_repaid += fine_amount_repaid

                    # record the fine transaction
                    fine_transaction_data = {
                        "user_id": current_user.id,
                        "amount": fine_amount_repaid,
                        "origin": wallet_id,
                        "activity_id": activity_id,
                        "transaction_date": transaction_date,
                        "updated_at": transaction_date,
                        "transaction_completed": True,
                        "transaction_code": fine_transaction_code,
                        "transaction_type": "late contribution",
                    }
                    new_fine_transaction = models.ActivityTransaction(
                        **fine_transaction_data
                    )
                    db.add(new_fine_transaction)

                    if amount == 0:
                        break

            # if after fine repayment, the member has some amount left, we contribute towards the expected amount
            user_record = (
                db.query(models.User).filter(models.User.id == current_user.id).first()
            )
            if amount > 0 and expected_amount > 0:
                transaction_code = generate_transaction_code(
                    "manual_contribution", wallet_id
                )

                if amount > expected_amount:
                    amount = expected_amount

                # record the transaction
                transaction_data = {
                    "user_id": current_user.id,
                    "amount": amount,
                    "origin": wallet_id,
                    "activity_id": activity_id,
                    "transaction_date": transaction_date,
                    "updated_at": transaction_date,
                    "transaction_completed": True,
                    "transaction_code": transaction_code,
                    "transaction_type": "contribution",
                }
                new_transaction = models.ActivityTransaction(**transaction_data)
                db.add(new_transaction)

                amount_contributed = amount

            # update the wallet balance
            user_record = (
                db.query(models.User).filter(models.User.id == current_user.id).first()
            )
            activity = (
                db.query(models.Activity)
                .filter(models.Activity.id == activity_id)
                .first()
            )
            user_record.wallet_balance -= amount_contributed + total_fines_repaid

            # update the activity account balance
            activity_account = (
                db.query(models.Activity_Account)
                .filter(models.Activity_Account.activity_id == activity_id)
                .first()
            )
            activity_account.account_balance += total_fines_repaid + amount_contributed

            # update the chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == activity.chama_id)
                .first()
            )
            chama_account.account_balance += total_fines_repaid + amount_contributed

            db.commit()

    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to contribute to merry go round {e}")
        raise HTTPException(
            status_code=400, detail="Failed to contribute to merry go round"
        )


# contribute t the generic activities
@router.post(
    "/contribute/generic/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def contribute_to_merry_go_round(
    activity_id: int,
    contrib_data: schemas.ContributeToActivityBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        expected_amount = contrib_data.expected_contribution
        amount = contrib_data.amount
        transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        wallet_id = (
            db.query(models.User.wallet_id)
            .filter(models.User.id == current_user.id)
            .scalar()
        )

        fines = (
            db.query(models.ActivityFine)
            .filter(
                and_(
                    models.ActivityFine.activity_id == activity_id,
                    models.ActivityFine.user_id == current_user.id,
                    models.ActivityFine.is_paid == False,
                )
            )
            .order_by(models.ActivityFine.fine_date)
            .with_for_update()  # lock the rows for update
            .all()
        )

        total_fines_repaid = 0
        amount_contributed = 0

        with db.begin_nested():
            if fines:
                for fine in fines:
                    fine_transaction_code = generate_transaction_code(
                        "manual_fine_repayment", wallet_id
                    )

                    if amount >= fine.expected_repayment:
                        amount -= fine.expected_repayment
                        fine_amount_repaid = fine.expected_repayment
                        fine.is_paid = True
                        fine.paid_date = transaction_date
                        fine.expected_repayment = 0
                    else:
                        fine.expected_repayment -= amount
                        fine_amount_repaid = amount
                        amount = 0

                    total_fines_repaid += fine_amount_repaid

                    # record the fine transaction
                    fine_transaction_data = {
                        "user_id": current_user.id,
                        "amount": fine_amount_repaid,
                        "origin": wallet_id,
                        "activity_id": activity_id,
                        "transaction_date": transaction_date,
                        "updated_at": transaction_date,
                        "transaction_completed": True,
                        "transaction_code": fine_transaction_code,
                        "transaction_type": "late contribution",
                    }
                    new_fine_transaction = models.ActivityTransaction(
                        **fine_transaction_data
                    )
                    db.add(new_fine_transaction)

                    if amount == 0:
                        break

            # if after fine repayment, the member has some amount left, we contribute towards the expected amount
            user_record = (
                db.query(models.User).filter(models.User.id == current_user.id).first()
            )
            if amount > 0 and expected_amount > 0:
                transaction_code = generate_transaction_code(
                    "manual_contribution", wallet_id
                )

                if amount > expected_amount:
                    amount = expected_amount

                # record the transaction
                transaction_data = {
                    "user_id": current_user.id,
                    "amount": amount,
                    "origin": wallet_id,
                    "activity_id": activity_id,
                    "transaction_date": transaction_date,
                    "updated_at": transaction_date,
                    "transaction_completed": True,
                    "transaction_code": transaction_code,
                    "transaction_type": "contribution",
                }
                new_transaction = models.ActivityTransaction(**transaction_data)
                db.add(new_transaction)

                amount_contributed = amount

            # update the wallet balance
            user_record = (
                db.query(models.User).filter(models.User.id == current_user.id).first()
            )
            activity = (
                db.query(models.Activity)
                .filter(models.Activity.id == activity_id)
                .first()
            )
            user_record.wallet_balance -= amount_contributed + total_fines_repaid

            # update the activity account balance
            activity_account = (
                db.query(models.Activity_Account)
                .filter(models.Activity_Account.activity_id == activity_id)
                .first()
            )
            activity_account.account_balance += total_fines_repaid + amount_contributed

            # update the chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == activity.chama_id)
                .first()
            )
            chama_account.account_balance += total_fines_repaid + amount_contributed

            db.commit()

    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to contribute to activity{e}")
        raise HTTPException(status_code=400, detail="Failed to contribute to activity")


# generate transaction code
def generate_transaction_code(transaction_type, wallet_id):
    # define a prefix for each transaction
    prefixes = {
        "auto_contribution": "AC",
        "auto_late_contribution": "ALC",
        "manual_contribution": "MC",
        "manual_fine_repayment": "MFR",
        "unprocessed wallet deposit": "UWD",
        "unprocessed registration fee": "URF",
        "unprocessed wallet withdrawal": "UWW",
    }

    # get the current timestamp - date - month - year - hour - minute - second
    timestamp = datetime.now(nairobi_tz).strftime("%d%m%Y%H%M%S")
    # generate a random 4-digit number to ensure uniqueness
    unique_number = random.randint(1000, 9999)

    # get the prefix for the transaction type
    # for unknown transaction types, use UNX
    prefix = prefixes.get(transaction_type, "UNX")

    # create the transaction code
    transaction_code = f"{prefix}_{wallet_id}-{timestamp}-{unique_number}"
    return transaction_code


# more recent transactions all round
@router.get(
    "/recent_transactions",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.MemberRecentTransactionResp],
)
async def get_recent_transactions(
    member_data: schemas.MemberRecentTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        transactions = (
            db.query(models.Transaction)
            .filter(
                and_(
                    models.Transaction.member_id == current_user.id,
                    models.Transaction.transaction_completed == True,
                    models.Transaction.is_reversed == False,
                    models.Transaction.transaction_type != "processed",
                )
            )
            .order_by(desc(models.Transaction.transaction_date))
            .limit(4)
            .all()
        )

        return [
            schemas.MemberRecentTransactionResp(
                amount=transaction.amount,
                chama_id=transaction.chama_id,
                transaction_type=transaction.transaction_type,
                transaction_date=transaction.transaction_date,
                transaction_origin=transaction.transaction_origin,
                transaction_completed=transaction.transaction_completed,
            )
            for transaction in transactions
        ]

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get members recent transactions"
        )


# update wallet balance
@router.put(
    "/deposit_to_wallet",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberWalletBalanceResp,
)
async def deposit_to_wallet(
    wallet_data: schemas.UpdateWalletBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        transaction_type = wallet_data.transaction_type
        amount = wallet_data.amount
        transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None)
        transaction_code = wallet_data.transaction_code
        transaction_destination = wallet_data.transaction_destination
        member_id = wallet_data.member_id

        with db.begin_nested():
            member = (
                db.query(models.User)
                .filter(models.User.id == member_id)
                .with_for_update()
                .first()
            )

            if not member:
                raise HTTPException(status_code=404, detail="Member not found")

            # update the members wallet balance
            member.wallet_balance += amount

            wallet_transaction = models.Wallet_Transaction(
                amount=amount,
                transaction_type=transaction_type,
                transaction_date=transaction_date,
                transaction_completed=True,
                transaction_code=transaction_code,
                transaction_destination=transaction_destination,
                member_id=member_id,
            )
            db.add(wallet_transaction)

            # callback record update
            callback_record = (
                db.query(models.CallbackData)
                .filter(
                    models.CallbackData.CheckoutRequestID == transaction_code,
                    models.CallbackData.Status == "Pending",
                    models.CallbackData.Amount == amount,
                    models.CallbackData.Purpose == "wallet",
                )
                .first()
            )
            transaction_info_logger.info(f"callback record {callback_record}")
            callback_record.Status = "Success"

        db.commit()
        return {"wallet_balance": member.wallet_balance}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        transaction_error_logger.error(f"Failed to update members wallet balance {e}")
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Failed to update members wallet balance"
        )


# get members wallet balance from members table
@router.get(
    "/wallet_balance",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberWalletBalanceResp,
)
async def get_member_wallet_balance(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        member = db.query(models.User).filter(models.User.id == current_user.id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        return {"wallet_balance": member.wallet_balance}

    except Exception as e:
        transaction_error_logger.error(f"Failed to get members wallet balance {e}")
        raise HTTPException(
            status_code=400, detail="Failed to get members wallet balance"
        )


# retrieve wallet activity for a member, latest 3 transactions
@router.get(
    "/recent_wallet_activity",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.WalletTransactionResp],
)
async def get_recent_wallet_activity(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        wallet_activity = (
            db.query(models.Wallet_Transaction)
            .filter(models.Wallet_Transaction.member_id == current_user.id)
            .filter(models.Wallet_Transaction.transaction_completed == True)
            .filter(
                models.Wallet_Transaction.transaction_type
                != "unprocessed wallet deposit"
            )
            .filter(
                models.Wallet_Transaction.transaction_type != "processed wallet deposit"
            )
            .order_by(desc(models.Wallet_Transaction.transaction_date))
            .limit(3)
            .all()
        )

        if not wallet_activity:
            raise HTTPException(
                status_code=404, detail="No wallet activity for this member"
            )

        return [
            schemas.WalletTransactionResp(
                amount=activity.amount,
                transaction_type=activity.transaction_type,
                transaction_completed=activity.transaction_completed,
                transaction_date=activity.transaction_date,
                transaction_destination=activity.transaction_destination,
            )
            for activity in wallet_activity
        ]

    except Exception as e:
        transaction_error_logger.error(
            f"Failed to get members recent wallet activity {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to get members recent wallet activity"
        )


# repaying fines for a member in a certain chama - we will pull all the unpaid fines for a member in a chama and loop through the earliest using fine_date, we we use the amout we receive from the member
# and the total_expected_amount in the fine table for deduction, after every deduction, we update the fine table, with a ew total_expected_amount and proceed to the next fine,


# might check on adding headers to the request to make sure the member is the one making the request
@router.post(
    "/unified_wallet_contribution",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UnifiedWalletContResp,
)
async def unified_wallet_contribution(
    contrib_data: schemas.UnifiedWalletContBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        transaction_info_logger.info(
            "===========unified wallet contribution==========="
        )
        chama_id = contrib_data.chama_id
        member_id = contrib_data.member_id
        amount = contrib_data.amount
        expected_amount = contrib_data.expected_contribution
        transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None)
        wallet_number = generateWalletNumber(db, member_id)

        fines = (
            db.query(models.Fine)
            .filter(
                and_(
                    models.Fine.chama_id == chama_id,
                    models.Fine.member_id == member_id,
                    models.Fine.is_paid == False,
                )
            )
            .order_by(models.Fine.fine_date)
            .with_for_update()
            .all()
        )

        total_fines_repaid = 0
        amount_contributed = 0
        with db.begin_nested():
            if fines:
                for fine in fines:
                    transaction_info_logger.info(
                        f"fine amout {fine.total_expected_amount}"
                    )
                    transaction_info_logger.info(f"paying with {amount}")

                    fine_transaction_code = generate_transaction_code(
                        "fine_repay", wallet_number, chama_id
                    )

                    if amount >= fine.total_expected_amount:
                        amount -= fine.total_expected_amount
                        fine_amount_repaid = fine.total_expected_amount
                        fine.is_paid = True
                        fine.paid_date = transaction_date
                        fine.total_expected_amount = 0
                    else:
                        fine.total_expected_amount -= amount
                        fine_amount_repaid = amount
                        amount = 0

                    total_fines_repaid += fine_amount_repaid

                    # record the fine transaction
                    fine_transaction_data = {
                        "amount": fine_amount_repaid,
                        "phone_number": wallet_number,
                        "transaction_date": transaction_date,
                        "updated_at": transaction_date,
                        "transaction_completed": True,
                        "transaction_code": fine_transaction_code,
                        "transaction_type": "fine deduction",
                        "transaction_origin": "wallet",
                        "chama_id": chama_id,
                        "member_id": member_id,
                    }
                    new_fine_transaction = models.Transaction(**fine_transaction_data)
                    db.add(new_fine_transaction)

                    # create a wallet transaction for fine deduction
                    wallet_fine_transaction_data = {
                        "amount": fine_amount_repaid,
                        "transaction_type": "fine deduction",
                        "transaction_date": transaction_date,
                        "transaction_completed": True,
                        "transaction_code": fine_transaction_code,
                        "transaction_destination": chama_id,
                        "member_id": member_id,
                    }
                    new_wallet_fine_transaction = models.Wallet_Transaction(
                        **wallet_fine_transaction_data
                    )
                    db.add(new_wallet_fine_transaction)

                    if amount == 0:
                        break

            # if after fine repayment, the member has some amount left, we contribute towards the expected amount
            # this is both a wallet and trasaction record
            member_record = (
                db.query(models.User).filter(models.User.id == member_id).first()
            )
            if amount > 0 and expected_amount > 0:
                transaction_code = generate_transaction_code(
                    "deposit", wallet_number, chama_id
                )

                if amount > expected_amount:
                    amount = expected_amount

                # record the transaction
                transaction_data = {
                    "amount": amount,
                    "phone_number": member_record.wallet_number,
                    "transaction_date": transaction_date,
                    "updated_at": transaction_date,
                    "transaction_completed": True,
                    "transaction_code": transaction_code,
                    "transaction_type": "deposit",
                    "transaction_origin": "wallet",
                    "chama_id": chama_id,
                    "member_id": member_id,
                }

                new_transaction = models.Transaction(**transaction_data)
                db.add(new_transaction)

                # record the wallet transaction
                wallet_transaction_data = {
                    "amount": amount,
                    "transaction_type": "moved to chama",
                    "transaction_date": transaction_date,
                    "transaction_completed": True,
                    "transaction_code": transaction_code,
                    "transaction_destination": chama_id,
                    "member_id": member_id,
                }

                new_wallet_transaction = models.Wallet_Transaction(
                    **wallet_transaction_data
                )
                db.add(new_wallet_transaction)

                amount_contributed = amount

            # update the wallet balance
            member_record = (
                db.query(models.User).filter(models.User.id == member_id).first()
            )
            member_record.wallet_balance -= amount_contributed + total_fines_repaid

            # update the chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == chama_id)
                .first()
            )
            chama_account.account_balance += total_fines_repaid + amount_contributed

            db.commit()

        transaction_info_logger.info(
            "===========unified wallet contribution==========="
        )
        return {"message": "unified wallet contribution successful"}
    except Exception as e:
        transaction_error_logger.error(f"failed to make a unified wallet cont {e}")
        db.rollback()
        raise HTTPException(
            status_code=400, detail="unified wallet contribution failed"
        )


# retrieve the amount of fines a member has in a chama
@router.get(
    "/total_fines",
    status_code=status.HTTP_200_OK,
    response_model=schemas.TotalFinesResp,
)
async def get_total_fines(
    fine_data: schemas.MemberFines = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        fine_dict = fine_data.dict()
        chama_id = fine_dict["chama_id"]
        member_id = fine_dict["member_id"]

        total_fine_amount = (
            db.query(func.coalesce(func.sum(models.Fine.total_expected_amount), 0))
            .filter(
                and_(
                    models.Fine.chama_id == chama_id,
                    models.Fine.member_id == member_id,
                    models.Fine.is_paid == False,
                )
            )
            .scalar()
        )

        return {"total_fines": total_fine_amount}

    except Exception as e:
        transaction_error_logger.error(f"Failed to get total fines {e}")
        raise HTTPException(status_code=400, detail="Failed to get total fines")


# check if a member is already joined a chama  using the chama id and member id and the members_chamas_association table
@router.get(
    "/member_in_chama",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ChamaMembershipResp,
)
async def check_chama_membership(
    chama_data: schemas.ChamaMembershipBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        chama_dict = chama_data.dict()
        chama_id = chama_dict["chama_id"]
        user_id = chama_dict["member_id"]

        chama_membership = (
            db.query(models.chama_user_association)
            .filter(
                and_(
                    models.chama_user_association.c.chama_id == chama_id,
                    models.chama_user_association.c.user_id == user_id,
                )
            )
            .first()
        )

        if not chama_membership:
            return {"is_member": False}

        return {"is_member": True}

    except Exception as e:
        transaction_error_logger.error(f"Failed to check chama membership {e}")
        raise HTTPException(status_code=400, detail="Failed to check chama membership")


@router.get(
    "/share_price_and_prev_two_contribution_dates",
    status_code=status.HTTP_200_OK,
)
async def get_share_price_and_prev_two_contribution_dates(
    db: Session = Depends(database.get_db),
):

    try:
        chamas = db.query(models.Chama).all()
        chamas_details = {}
        for chama in chamas:
            chama_contribution_day = (
                db.query(models.ChamaContributionDay)
                .filter(models.ChamaContributionDay.chama_id == chama.id)
                .first()
            )
            if not chama_contribution_day:
                raise HTTPException(
                    status_code=404, detail="Chama contribution day not found"
                )

            prev_contribution_date, prev_two_contribution_date = (
                calculate_two_previous_dates(
                    chama.contribution_interval,
                    chama_contribution_day.next_contribution_date,
                )
            )

            chamas_details[chama.id] = {
                "share_price": chama.contribution_amount,
                "fine_per_share": chama.fine_per_share,
                "prev_contribution_date": prev_contribution_date,
                "prev_two_contribution_date": prev_two_contribution_date,
            }

        transaction_info_logger.info(
            "Chamas share price and previous two contribution dates retrieved"
        )

        return chamas_details
    except Exception as e:
        transaction_error_logger.error(
            f"Failed to retrieve chamas share price and previous two contribution dates {e}"
        )
        raise HTTPException(
            status_code=400,
            detail="Failed to retrieve chamas share price and previous two contribution dates",
        )


# using interval and the next contribution date, get the previous two contribution dates
# i.e next date = 2024-06-23 08:40:07.801134
# interval = weekly or daily or monthly
# contribution_day = Monday or Tuesday or Wednesday or Thursday or Friday or Saturday or Sunday
def calculate_two_previous_dates(interval, next_contribution_date):
    prev_contribution_date = None
    prev_two_contribution_date = None
    if interval == "daily":
        prev_contribution_date = next_contribution_date - timedelta(days=1)
        prev_two_contribution_date = next_contribution_date - timedelta(days=2)
    elif interval == "weekly":
        prev_contribution_date = next_contribution_date - timedelta(weeks=1)
        prev_two_contribution_date = next_contribution_date - timedelta(weeks=2)
    elif interval == "monthly":
        prev_contribution_date = next_contribution_date - timedelta(weeks=4)
        prev_two_contribution_date = next_contribution_date - timedelta(weeks=8)
    return prev_contribution_date, prev_two_contribution_date


# using the chama details dreturned above, the share price, the fine, and two prev dates, check between those dates and check a members total contribution between those dates, compare
# to the expected contribution (share price * num of shares (from members_chamas table)) and calculate the difference.
# if its > 0, the member is behind in that chamas contribution for that period and is assinged a fine per share to be added as a record in the fines table
# chama_id, member_id, fine, fine_reason, fine_date(prev_contrib_date), is_paid, paid_date, total_expected_amount(total fine + missed contribution amount)
@router.post(
    "/setting_chama_members_contribution_fines",
    status_code=status.HTTP_201_CREATED,
)
async def setting_members_contribution_fines(
    chama_details: dict,
    db: Session = Depends(database.get_db),
):
    try:
        transaction_info_logger.info("=====setting members contribution fines========")
        fines = {}
        for chama_id, details in chama_details.items():
            chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
            if not chama:
                continue
            transaction_info_logger.info(f"chama {chama_id}")

            last_contribution_datetime = datetime.fromisoformat(
                details["prev_contribution_date"]
            )
            second_last_contribution_datetime = datetime.fromisoformat(
                details["prev_two_contribution_date"]
            )

            members = (
                db.query(models.User)
                .join(models.chama_user_association)
                .options(joinedload(models.User.chamas))
                .filter(models.chama_user_association.c.chama_id == chama_id)
                .filter(models.chama_user_association.c.registration_fee_paid == True)
                .all()
            )

            for member in members:
                member_chama = (
                    db.query(models.chama_user_association)
                    .filter(
                        and_(
                            models.chama_user_association.c.member_id == member.id,
                            models.chama_user_association.c.chama_id == chama_id,
                        )
                    )
                    .first()
                )

                if not member_chama:
                    continue

                total_contribution = (
                    db.query(func.coalesce(func.sum(models.Transaction.amount), 0))
                    .filter(
                        and_(
                            models.Transaction.member_id == member.id,
                            models.Transaction.chama_id == chama_id,
                            models.Transaction.transaction_type == "deposit",
                            models.Transaction.transaction_completed == True,
                            models.Transaction.is_reversed == False,
                            func.date(models.Transaction.transaction_date)
                            > second_last_contribution_datetime.date(),
                            func.date(models.Transaction.transaction_date)
                            <= last_contribution_datetime.date(),
                        )
                    )
                    .scalar()
                )

                expected_contribution = (
                    chama.contribution_amount * member_chama.num_of_shares
                )
                difference = expected_contribution - total_contribution

                if difference > 0:
                    fine = member_chama.num_of_shares * chama.fine_per_share
                    fine_data = {
                        "chama_id": chama_id,
                        "member_id": member.id,
                        "fine": fine,
                        "fine_reason": "missed contribution",
                        "fine_date": details["prev_contribution_date"],
                        "is_paid": False,
                        "paid_date": None,
                        "total_expected_amount": fine + difference,
                    }

                    existing_fine = (
                        db.query(models.Fine)
                        .filter(
                            and_(
                                models.Fine.member_id == member.id,
                                models.Fine.chama_id == chama_id,
                                func.date(models.Fine.fine_date)
                                == last_contribution_datetime.date(),
                            )
                        )
                        .first()
                    )

                    if not existing_fine:
                        transaction_info_logger.info(f"fine {fine_data}")
                        new_fine = models.Fine(**fine_data)
                        db.add(new_fine)
                        db.commit()
                        db.refresh(new_fine)

        transaction_info_logger.info("=====members contribution fines set========")
        return {"message": "fines set successfully"}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to set members contribution fines {e}")
        raise HTTPException(
            status_code=400,
            detail="Failed to set members contribution fines",
        )


# return the fine amount of one individual member in a chama
@router.get(
    "/member_fine/{chama_id}/{member_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.TotalFinesResp,
)
async def get_member_fine(
    chama_id: int,
    member_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        total_fines = (
            db.query(func.coalesce(func.sum(models.Fine.total_expected_amount), 0))
            .filter(
                and_(
                    models.Fine.chama_id == chama_id,
                    models.Fine.member_id == member_id,
                    models.Fine.is_paid == False,
                )
            )
            .scalar()
        )

        return {"total_fines": total_fines}
    except Exception as e:
        transaction_error_logger.error(f"Failed to get member fine {e}")
        raise HTTPException(status_code=400, detail="Failed to get member fine")


# create an auto contribution for a member in a chama
@router.post("/auto_contribute/{activity_id}", status_code=status.HTTP_201_CREATED)
async def set_auto_contribute(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        # add a record to the auto_contribution table
        contribution_amount = (
            db.query(models.Activity.activity_amount)
            .filter(models.Activity.id == activity_id)
            .one_or_none()
        )
        if not contribution_amount:
            raise HTTPException(status_code=404, detail="Activity not found")

        print("contrib:", contribution_amount)

        # users shares in this activity from tha activites_user_association table
        user_shares = (
            db.query(models.activity_user_association.c.shares)
            .filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_id == current_user.id,
                )
            )
            .one_or_none()
        )

        print("user shares:", user_shares)

        if not user_shares:
            raise HTTPException(
                status_code=404, detail="User shares in this activity not found"
            )

        # retrieve the next contribtion date for this activity
        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )
        if not next_contribution_date:
            raise HTTPException(
                status_code=404, detail="Next contribution date not found"
            )

        auto_contribution_data = {
            "user_id": current_user.id,
            "activity_id": activity_id,
            "expected_amount": contribution_amount[0] * user_shares[0],
            "next_contribution_date": next_contribution_date,
        }

        new_auto_contribution = models.AutoContribution(**auto_contribution_data)
        db.add(new_auto_contribution)

        db.commit()

        return {"message": "Auto contribution set successfully"}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to set auto contribution {e}")
        raise HTTPException(status_code=400, detail="Failed to set auto contribution")


# stop auto contribution for a user in an activity by removing the record from the auto_contribution table
@router.delete("/auto_contribute/{activity_id}", status_code=status.HTTP_200_OK)
async def stop_auto_contribute(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        auto_record = (
            db.query(models.AutoContribution)
            .filter(
                and_(
                    models.AutoContribution.activity_id == activity_id,
                    models.AutoContribution.user_id == current_user.id,
                )
            )
            .first()
        )

        if not auto_record:
            raise HTTPException(
                status_code=404, detail="Auto contribution record not found"
            )

        db.delete(auto_record)
        db.commit()

        return {"message": "Auto contribution stopped successfully"}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to stop auto contribution {e}")
        raise HTTPException(status_code=400, detail="Failed to stop auto contribution")


# check if autocontribute status is set for a member in a chama
@router.get(
    "/auto_contribute_status/{activity_id}/{user_id}", status_code=status.HTTP_200_OK
)
async def check_auto_contribute_status(
    activity_id: int,
    user_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        auto_contribute_status = (
            db.query(models.AutoContribution)
            .filter(
                and_(
                    models.AutoContribution.activity_id == activity_id,
                    models.AutoContribution.user_id == user_id,
                )
            )
            .first()
        )

        if not auto_contribute_status:
            return {"status": "inactive"}

        return {"status": "active"}
    except Exception as e:
        transaction_error_logger.error(f"Failed to check auto contribute status {e}")
        raise HTTPException(
            status_code=400, detail="Failed to check auto contribute status"
        )


# making auto contribution to an activity
# 1. get all the records of auto coontribution whose next_day_contribution_date is today and the member has a wallet balance > 0
# 2. retrieve any fines the users has and deduct from the wallet balance
# 3. if any bal after fine repayment, move on to make a contribution to the activity either partially or fully depending on the wallet balance
# 4. update the wallet balance and the activity account balance and the chama account balance
@router.post(
    "/make_activity_auto_contributions",
    status_code=status.HTTP_201_CREATED,
)
async def make_auto_contributions(
    db: Session = Depends(database.get_db),
):

    try:
        today = datetime.now(nairobi_tz).date()

        # retrieve all auto_records whose next_contribution_date is today and the member has a wallet balance > 0
        auto_records = (
            db.query(
                models.AutoContribution,
                models.User.wallet_balance,
                models.User.wallet_id,
                models.User.id,
                models.AutoContribution.activity_id,
                models.AutoContribution.expected_amount,
                models.Activity.chama_id,
            )
            .join(models.User, models.User.id == models.AutoContribution.user_id)
            .join(
                models.Activity,
                models.Activity.id == models.AutoContribution.activity_id,
            )
            .filter(
                and_(
                    func.date(models.AutoContribution.next_contribution_date) > today,
                    models.User.wallet_balance > 0,
                )
            )
            .all()
        )

        if not auto_records:
            return {"message": "No auto contributions to make today"}

        # display the records
        print("=====autorecords=====")
        for record in auto_records:
            print(record)
        print()

        # fetch user fines in bulk for all users involved
        user_ids = [record.id for record in auto_records]
        activity_ids = [record.activity_id for record in auto_records]
        fines = (
            db.query(models.ActivityFine)
            .filter(
                models.ActivityFine.user_id.in_(user_ids),
                models.ActivityFine.is_paid == False,
                models.ActivityFine.activity_id.in_(activity_ids),
            )
            .all()
        )

        print("=====fines=====")
        for fine in fines:
            print(fine)
        print()

        # organize fines by the user_id
        fines_by_user = {}
        for fine in fines:
            fines_by_user.setdefault(fine.user_id, []).append(fine)

        print("=====fines by user=====")
        for user_id, user_fines in fines_by_user.items():
            print(user_id, user_fines)
        print()

        activity_transactions = []
        user_updates = []
        activity_updates = {}
        chama_updates = {}

        with db.begin_nested():
            for record in auto_records:
                expected_amount = record.expected_amount
                wallet_balance = record.wallet_balance
                wallet_id = record.wallet_id
                total_fines_repaid = 0

                # get fines for the user if any
                user_fines = fines_by_user.get(record.id, [])
                print("===user fines===\n", user_fines)

                # deduct fines from the wallet balance
                for fine in user_fines:
                    print("===wallet balance===", wallet_balance)
                    fine_amount_deducted = min(wallet_balance, fine.expected_repayment)
                    wallet_balance -= fine_amount_deducted
                    fine.expected_repayment -= fine_amount_deducted
                    total_fines_repaid += fine_amount_deducted
                    print("===fine amount deducted===", fine_amount_deducted)
                    print("===fine expected repayment===", fine.expected_repayment)
                    print("===wallet balance after fine deduction===", wallet_balance)
                    print("===total fines repaid===", total_fines_repaid)

                    if fine.expected_repayment == 0:
                        fine.is_paid = True
                        fine.paid_date = datetime.now(nairobi_tz).replace(
                            tzinfo=None, microsecond=0
                        )

                    # lof fine repayment transaction
                    transaction_code = generate_transaction_code(
                        "auto_late_contribution", wallet_id
                    )
                    transaction_date = datetime.now(nairobi_tz).replace(
                        tzinfo=None, microsecond=0
                    )
                    activity_transactions.append(
                        models.ActivityTransaction(
                            user_id=record.id,
                            amount=fine_amount_deducted,
                            origin=wallet_id,
                            activity_id=record.activity_id,
                            transaction_date=transaction_date,
                            updated_at=transaction_date,
                            transaction_completed=True,
                            transaction_code=transaction_code,
                            transaction_type="late contribution",
                        )
                    )

                    print("last wallet balance", wallet_balance)
                    if wallet_balance == 0:
                        break

                # skip if no balance left after fines
                if wallet_balance == 0:
                    # update the wallet balance
                    user_updates.append(
                        {
                            "user_id": record.id,
                            "wallet_balance": wallet_balance,
                        }
                    )

                    # update activity account balance
                    activity_updates[record.activity_id] = (
                        activity_updates.get(record.activity_id, 0) + total_fines_repaid
                    )

                    # update chama account balance
                    chama_updates[record.chama_id] = (
                        chama_updates.get(record.chama_id, 0) + total_fines_repaid
                    )
                    continue

                print("==expected==", expected_amount)
                print("==wallet balance==", wallet_balance)
                # calculate contribution
                contributed_so_far = get_member_activity_contribution_so_far(
                    record.id, record.activity_id, db
                )["total_contribution"]
                print("==so far==", contributed_so_far)
                remaining_contribution = max(0, expected_amount - contributed_so_far)
                print("==remaining==", remaining_contribution)

                # Actual contribution based on remaining wallet balance
                actual_contribution = min(remaining_contribution, wallet_balance)
                if actual_contribution > 0:
                    transaction_code = generate_transaction_code(
                        "auto_contribution", wallet_id
                    )
                    transaction_date = datetime.now(nairobi_tz).replace(
                        tzinfo=None, microsecond=0
                    )
                    activity_transactions.append(
                        models.ActivityTransaction(
                            user_id=record.id,
                            amount=actual_contribution,
                            origin=wallet_id,
                            activity_id=record.activity_id,
                            transaction_date=transaction_date,
                            updated_at=transaction_date,
                            transaction_completed=True,
                            transaction_code=transaction_code,
                            transaction_type="contribution",
                        )
                    )

                    wallet_balance -= actual_contribution

                # update the wallet balance
                user_updates.append(
                    {
                        "user_id": record.id,
                        "wallet_balance": wallet_balance,
                    }
                )

                # update activity account balance
                activity_updates[record.activity_id] = (
                    activity_updates.get(record.activity_id, 0)
                    + actual_contribution
                    + total_fines_repaid
                )

                # update chama account balance
                chama_updates[record.chama_id] = (
                    chama_updates.get(record.chama_id, 0)
                    + actual_contribution
                    + total_fines_repaid
                )

            # update the database bulk
            db.bulk_save_objects(activity_transactions)

            # update the wallet balances
            for update in user_updates:
                db.query(models.User).filter(
                    models.User.id == update["user_id"]
                ).update({"wallet_balance": update["wallet_balance"]})

            # update the activity account balances
            for activity_id, amount in activity_updates.items():
                db.query(models.Activity_Account).filter(
                    models.Activity_Account.id == activity_id
                ).update(
                    {
                        "account_balance": models.Activity_Account.account_balance
                        + amount
                    }
                )

            # update the chama account balances in bulk
            for chama_id, amount in chama_updates.items():
                db.query(models.Chama_Account).filter(
                    models.Chama_Account.id == chama_id
                ).update(
                    {"account_balance": models.Chama_Account.account_balance + amount}
                )

            db.commit()

        return {"message": "Auto contributions made successfully"}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to make auto contributions {e}")
        raise HTTPException(status_code=400, detail="Failed to make auto contributions")


def get_member_activity_contribution_so_far(user_id, activity_id, db):
    try:
        contribution_dates = (
            db.query(models.ActivityContributionDate)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .first()
        )
        prev_contribution_date = contribution_dates.previous_contribution_date.date()
        next_contribution_date = contribution_dates.next_contribution_date.date()

        # rewrite the above query to sum the amount using coalesce
        total_contributions = (
            db.query(func.coalesce(func.sum(models.ActivityTransaction.amount), 0))
            .filter(
                and_(
                    models.ActivityTransaction.user_id == user_id,
                    models.ActivityTransaction.activity_id == activity_id,
                    models.ActivityTransaction.transaction_completed == True,
                    models.ActivityTransaction.transaction_type == "contribution",
                    models.ActivityTransaction.is_reversed == False,
                    func.date(models.ActivityTransaction.transaction_date)
                    > prev_contribution_date,
                    func.date(models.ActivityTransaction.transaction_date)
                    <= next_contribution_date,
                )
            )
            .scalar()
        )

        return {"total_contribution": total_contributions}
    except Exception as e:
        transaction_error_logger.error(f"Failed to get member contribution so far {e}")
        raise HTTPException(
            status_code=400, detail="Failed to get members contribution so far"
        )


def difference_between_contributed_and_expected(
    db, member_id, chama_id, expected_amount
):
    # retrieve the interval and calcculate the previous contribution date - this will be period we will be cchecking the contributions
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        return expected_amount

    chama_contribution_day = (
        db.query(models.ChamaContributionDay)
        .filter(models.ChamaContributionDay.chama_id == chama_id)
        .first()
    )
    if not chama_contribution_day:
        return expected_amount

    upcoming_contribution_date = chama_contribution_day.next_contribution_date
    prev_contribution_date, second_prev_contribution_date = (
        calculate_two_previous_dates(
            chama.contribution_interval, upcoming_contribution_date
        )
    )

    total_contribution = (
        db.query(func.coalesce(func.sum(models.Transaction.amount), 0))
        .filter(
            and_(
                models.Transaction.member_id == member_id,
                models.Transaction.chama_id == chama_id,
                models.Transaction.transaction_type == "deposit",
                models.Transaction.transaction_completed == True,
                models.Transaction.is_reversed == False,
                func.date(models.Transaction.transaction_date)
                > prev_contribution_date.date(),
                func.date(models.Transaction.transaction_date)
                <= upcoming_contribution_date.date(),
            )
        )
        .scalar()
    )

    return expected_amount - total_contribution


# retrieve the wallet number
@router.get(
    "/wallet_number/{member_id}",
    status_code=status.HTTP_200_OK,
)
async def get_wallet_number(
    member_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        wallet_number = (
            db.query(models.User.wallet_id).filter(models.User.id == member_id).scalar()
        )

        return {"wallet_number": wallet_number}
    except Exception as e:
        transaction_error_logger.error(f"Failed to get wallet number {e}")
        raise HTTPException(status_code=400, detail="Failed to get wallet number")


def generateWalletNumber(db, member_id):
    wallet_number = (
        db.query(models.User.wallet_id).filter(models.User.id == member_id).scalar()
    )
    return wallet_number


# retrieve the transaction_fee for a transaction from the chamazetu_to_mpesa table
@router.get(
    "/chamazetu_to_mpesa_fee/{amount}",
    status_code=status.HTTP_200_OK,
)
async def get_chamazetu_to_mpesa_fee(
    amount: int,
    db: Session = Depends(database.get_db),
):

    try:
        print("==========fees=========")
        transaction_fee = (
            db.query(models.ChamazetuToMpesaFees.chamazetu_to_mpesa)
            .filter(
                and_(
                    models.ChamazetuToMpesaFees.from_amount <= amount,
                    models.ChamazetuToMpesaFees.to_amount >= amount,
                )
            )
            .scalar()
        )

        return {"transaction_fee": transaction_fee}
    except Exception as e:
        transaction_error_logger.error(f"Failed to get transaction fee {e}")
        raise HTTPException(status_code=400, detail="Failed to get transaction fee")
