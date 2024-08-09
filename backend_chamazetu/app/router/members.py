from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy import func, update, and_, table, column, desc
from sqlalchemy.orm import Session, joinedload
from typing import Union
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import logging, random
from typing import List
from uuid import uuid4

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/members", tags=["members"])

nairobi_tz = ZoneInfo("Africa/Nairobi")

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")


# get wallet number and balance
@router.get("/wallet_info/{member_id}", status_code=status.HTTP_200_OK)
async def get_wallet_info(
    member_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        member = db.query(models.Member).filter(models.Member.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        return {
            "wallet_number": member.wallet_number,
            "wallet_balance": member.wallet_balance,
        }

    except Exception as e:
        transaction_error_logger.error(f"Failed to get wallet info {e}")
        raise HTTPException(status_code=400, detail="Failed to get wallet info")


# get all chamas a member is connected to using member id
@router.get(
    "/chamas",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.MemberChamasResp],
)
async def get_member_chamas(
    current_user: models.Member = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):

    try:
        member_chamas = (
            db.query(models.Chama)
            .join(
                models.members_chamas_association,
                models.Chama.id == models.members_chamas_association.c.chama_id,
            )
            .filter(models.members_chamas_association.c.member_id == current_user.id)
            .all()
        )

        return [schemas.MemberChamasResp.from_orm(chama) for chama in member_chamas]

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to get member chamas")


# get members number of shares in a certain chama
@router.get(
    "/expected_contribution",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberSharesResp,
)
async def get_member_shares(
    shares_data: schemas.MemberSharesBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        shares_dict = shares_data.dict()
        chama_id = shares_dict["chama_id"]
        member_id = shares_dict["member_id"]

        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        chama_share_price = chama.contribution_amount

        member_shares = (
            db.query(models.members_chamas_association)
            .filter(
                and_(
                    models.members_chamas_association.c.chama_id == chama_id,
                    models.members_chamas_association.c.member_id == member_id,
                )
            )
            .first()
        )

        if not member_shares:
            raise HTTPException(status_code=404, detail="Member shares not found")

        member_expected_contribution = chama_share_price * member_shares.num_of_shares

        return {"member_expected_contribution": member_expected_contribution}

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get members expected contribution amount"
        )


# what a member has contributed to a chama from previous chama day to the next chama day
@router.get(
    "/member_contribution_so_far",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberContributionResp,
)
async def get_member_contribution_so_far(
    member_data: schemas.MemberContributionBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        member_dict = member_data.dict()
        chama_id = member_dict["chama_id"]
        member_id = member_dict["member_id"]
        previous_contribution_date = datetime.strptime(
            member_dict["previous_contribution_date"], "%d-%m-%Y"
        ).date()
        upcoming_contribution_date = datetime.strptime(
            member_dict["upcoming_contribution_date"], "%d-%m-%Y"
        ).date()

        member_contribution = (
            db.query(func.sum(models.Transaction.amount))
            .filter(
                and_(
                    models.Transaction.chama_id == chama_id,
                    models.Transaction.member_id == member_id,
                    models.Transaction.transaction_completed == True,
                    models.Transaction.is_reversed == False,
                    models.Transaction.transaction_type == "deposit",
                    func.date(models.Transaction.date_of_transaction)
                    > previous_contribution_date,
                    func.date(models.Transaction.date_of_transaction)
                    <= upcoming_contribution_date,
                )
            )
            .scalar()
        )

        if not member_contribution:
            member_contribution = 0

        return {"member_contribution": member_contribution}

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get members contribution so far"
        )


# mre recent transactions all round
@router.get(
    "/recent_transactions",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.MemberRecentTransactionResp],
)
async def get_recent_transactions(
    member_data: schemas.MemberRecentTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
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
            .order_by(desc(models.Transaction.date_of_transaction))
            .limit(4)
            .all()
        )

        return [
            schemas.MemberRecentTransactionResp(
                amount=transaction.amount,
                chama_id=transaction.chama_id,
                transaction_type=transaction.transaction_type,
                date_of_transaction=transaction.date_of_transaction,
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
                db.query(models.Member)
                .filter(models.Member.id == member_id)
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
    current_user: models.Member = Depends(oauth2.get_current_user),
):

    try:
        member = (
            db.query(models.Member).filter(models.Member.id == current_user.id).first()
        )

        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        return {"wallet_balance": member.wallet_balance}

    except Exception as e:
        print(e)
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
    current_user: models.Member = Depends(oauth2.get_current_user),
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
                        "date_of_transaction": transaction_date,
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
                db.query(models.Member).filter(models.Member.id == member_id).first()
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
                    "date_of_transaction": transaction_date,
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
                db.query(models.Member).filter(models.Member.id == member_id).first()
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


# TODO: FIX LATER TO ONE WITH ABOVE OR BETTER IN RECORD FINE FROM MPESA ONLY
@router.put(
    "/repay_fines_from_mpesa",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberFineResp,
)
async def repay_fines(
    fine_data: schemas.MemberMpesaFineBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        transaction_info_logger.info("===========repaying fines===========")
        fine_dict = fine_data.dict()
        chama_id = fine_dict["chama_id"]
        member_id = fine_dict["member_id"]
        amount = fine_dict["amount"]
        phone_number = fine_dict["phone_number"]
        transaction_code = fine_dict["transaction_code"]

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

        if not fines:
            #  this means the member has no fines to pay so we return the amount to the member fror the transaction to be completed
            return {"balance_after_fines": amount}

        total_fines_repaid = 0
        with db.begin_nested():
            for fine in fines:
                transaction_info_logger.info(f"fine amout {fine.total_expected_amount}")
                transaction_info_logger.info(f"paying with {amount}")

                fine_transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None)

                if amount >= fine.total_expected_amount:
                    amount -= fine.total_expected_amount
                    fine_amount_repaid = fine.total_expected_amount
                    fine.is_paid = True
                    fine.paid_date = fine_transaction_date
                    fine.total_expected_amount = 0
                else:
                    fine.total_expected_amount -= amount
                    fine_amount_repaid = amount
                    amount = 0

                total_fines_repaid += fine_amount_repaid

                # record the fine transaction
                fine_transaction_data = {
                    "amount": fine_amount_repaid,
                    "phone_number": phone_number,
                    "date_of_transaction": fine_transaction_date,
                    "updated_at": fine_transaction_date,
                    "transaction_completed": True,
                    "transaction_code": transaction_code,
                    "transaction_type": "fine deduction",
                    "transaction_origin": "direct_deposit",
                    "chama_id": chama_id,
                    "member_id": member_id,
                }
                new_fine_transaction = models.Transaction(**fine_transaction_data)
                db.add(new_fine_transaction)

                if amount == 0:
                    break

            # update the chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == chama_id)
                .first()
            )
            chama_account.account_balance += total_fines_repaid

            db.commit()

        transaction_info_logger.info("===========mpesa fines repaid===========")
        # now return the balance after fines have been deducted from the initial amount
        return {"balance_after_fines": amount}
    except Exception as e:
        transaction_error_logger.error(f"Failed to repay fines {e}")
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to repay fines")


# ================================================================


# checking if a member has any fines to pay in a chama
@router.get(
    "/fines",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberFinesResp,
)
async def check_fines(
    fine_data: schemas.MemberFines = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        fine_dict = fine_data.dict()
        chama_id = fine_dict["chama_id"]
        member_id = fine_dict["member_id"]

        fines = (
            db.query(models.Fine)
            .filter(
                and_(
                    models.Fine.chama_id == chama_id,
                    models.Fine.member_id == member_id,
                    models.Fine.is_paid == False,
                )
            )
            .all()
        )

        if not fines:
            # return false if the member has no fines to pay
            return {"has_fines": False}

        total_fine_amount = 0
        for fine in fines:
            total_fine_amount += fine.total_expected_amount

        # return true if the member has fines to pay

        return {"has_fines": total_fine_amount > 0}

    except Exception as e:
        transaction_error_logger.error(f"Failed to check fines {e}")
        raise HTTPException(status_code=400, detail="Failed to check fines")


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
        member_id = chama_dict["member_id"]

        chama_membership = (
            db.query(models.members_chamas_association)
            .filter(
                and_(
                    models.members_chamas_association.c.chama_id == chama_id,
                    models.members_chamas_association.c.member_id == member_id,
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
                db.query(models.Member)
                .join(models.members_chamas_association)
                .options(joinedload(models.Member.chamas))
                .filter(models.members_chamas_association.c.chama_id == chama_id)
                .filter(
                    models.members_chamas_association.c.registration_fee_paid == True
                )
                .all()
            )

            for member in members:
                member_chama = (
                    db.query(models.members_chamas_association)
                    .filter(
                        and_(
                            models.members_chamas_association.c.member_id == member.id,
                            models.members_chamas_association.c.chama_id == chama_id,
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
                            func.date(models.Transaction.date_of_transaction)
                            > second_last_contribution_datetime.date(),
                            func.date(models.Transaction.date_of_transaction)
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
@router.post("/auto_contribute", status_code=status.HTTP_201_CREATED)
async def set_auto_contribute(
    auto_contribute_data: schemas.AutoContributeBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        chama_id = auto_contribute_data.chama_id
        member_id = auto_contribute_data.member_id
        expected_amount = auto_contribute_data.expected_amount
        next_contribution_date = auto_contribute_data.next_contribution_date

        auto_contribution = (
            db.query(models.AutoContribution)
            .filter(
                and_(
                    models.AutoContribution.chama_id == chama_id,
                    models.AutoContribution.member_id == member_id,
                )
            )
            .first()
        )

        if auto_contribution:
            raise HTTPException(
                status_code=400, detail="Auto contribution already set for this member"
            )

        auto_contribution_data = {
            "chama_id": chama_id,
            "member_id": member_id,
            "expected_amount": expected_amount,
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


# stop auto contribution for a member in a chama by removing the record from the auto_contribution table
@router.delete(
    "/auto_contribute/{chama_id}/{member_id}", status_code=status.HTTP_200_OK
)
async def stop_auto_contribute(
    chama_id: int,
    member_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        auto_contribution = (
            db.query(models.AutoContribution)
            .filter(
                and_(
                    models.AutoContribution.chama_id == chama_id,
                    models.AutoContribution.member_id == member_id,
                )
            )
            .first()
        )

        if not auto_contribution:
            raise HTTPException(
                status_code=404, detail="Auto contribution record not found"
            )

        db.delete(auto_contribution)
        db.commit()
        return {"message": "Auto contribution stopped successfully"}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to stop auto contribution {e}")
        raise HTTPException(status_code=400, detail="Failed to stop auto contribution")


# check if autocontribute status is set for a member in a chama
@router.get(
    "/auto_contribute_status/{chama_id}/{member_id}", status_code=status.HTTP_200_OK
)
async def check_auto_contribute_status(
    chama_id: int,
    member_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        auto_contribute_status = (
            db.query(models.AutoContribution)
            .filter(
                and_(
                    models.AutoContribution.chama_id == chama_id,
                    models.AutoContribution.member_id == member_id,
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


# auto contribution for a member in a chama
@router.post(
    "/make_auto_contributions",
    status_code=status.HTTP_201_CREATED,
)
async def auto_contrmake_auto_contributionsibute(
    db: Session = Depends(database.get_db),
):

    try:
        print("===========auto contribute===========")
        members = (
            db.query(models.AutoContribution)
            .filter(
                func.date(models.AutoContribution.next_contribution_date)
                == datetime.now(nairobi_tz).date()
            )
            .all()
        )

        with db.begin_nested():
            for member in members:
                wallet_balance = (
                    db.query(models.Member.wallet_balance)
                    .filter(models.Member.id == member.member_id)
                    .scalar()
                )
                print(f"{member.member_id} wallet balance {wallet_balance}")

                # here we will check if user has already made any deposits/contributions and update the expected amount
                expected_amount = difference_between_contributed_and_expected(
                    db, member.member_id, member.chama_id, member.expected_amount
                )
                print(f"expected amount {expected_amount}")

                # skip if the expected amount is 0
                if expected_amount <= 0:
                    continue

                # retrieve the fines for the member
                member_fines = (
                    db.query(models.Fine)
                    .filter(
                        and_(
                            models.Fine.member_id == member.member_id,
                            models.Fine.chama_id == member.chama_id,
                            models.Fine.is_paid == False,
                        )
                    )
                    .all()
                )

                if not member_fines:
                    if wallet_balance < expected_amount:
                        continue

                total_fines_deducted = 0

                # loop through the fines and deduct them from the wallet
                for fine in member_fines:
                    print(f"fine {fine.total_expected_amount}")
                    fine_transaction_date = datetime.now(nairobi_tz).replace(
                        tzinfo=None
                    )
                    fine_transaction_code = generate_transaction_code(
                        "auto_repay", "wallet", "fine"
                    )

                    if wallet_balance < fine.total_expected_amount:
                        fine.total_expected_amount -= wallet_balance
                        fine_amount_deducted = wallet_balance
                        wallet_balance = 0
                    else:
                        fine_amount_deducted = fine.total_expected_amount
                        wallet_balance -= fine.total_expected_amount
                        fine.total_expected_amount = 0
                        fine.is_paid = True
                        fine.paid_date = fine_transaction_date

                    total_fines_deducted += fine_amount_deducted

                    # record the fine transaction as one amount transaction
                    fine_transaction_data = {
                        "amount": fine_amount_deducted,
                        "phone_number": generateWalletNumber(db, member.member_id),
                        "date_of_transaction": fine_transaction_date,
                        "updated_at": fine_transaction_date,
                        "transaction_completed": True,
                        "transaction_code": fine_transaction_code,
                        "transaction_type": "fine deduction",
                        "transaction_origin": "wallet_deposit",
                        "chama_id": member.chama_id,
                        "member_id": member.member_id,
                    }

                    new_fine_transaction = models.Transaction(**fine_transaction_data)
                    db.add(new_fine_transaction)

                    # create a wallet transaction for fine deduction
                    wallet_fine_transaction_data = {
                        "amount": fine_amount_deducted,
                        "transaction_type": "fine deduction",
                        "transaction_date": fine_transaction_date,
                        "transaction_completed": True,
                        "transaction_code": fine_transaction_code,
                        "transaction_destination": member.chama_id,
                        "member_id": member.member_id,
                    }

                    new_wallet_fine_transaction = models.Wallet_Transaction(
                        **wallet_fine_transaction_data
                    )
                    db.add(new_wallet_fine_transaction)

                    if wallet_balance == 0:
                        break

                if wallet_balance < expected_amount:
                    continue

                # continue with the contribution
                # make a transaction
                transaction_code = generate_transaction_code(
                    "auto_deposit", "wallet", "chama"
                )
                transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None)
                transaction_data = {
                    "amount": expected_amount,
                    "phone_number": generateWalletNumber(db, member.member_id),
                    "date_of_transaction": transaction_date,
                    "updated_at": transaction_date,
                    "transaction_completed": True,
                    "transaction_code": transaction_code,
                    "transaction_type": "deposit",
                    "transaction_origin": "wallet_deposit",
                    "chama_id": member.chama_id,
                    "member_id": member.member_id,
                }

                new_transaction = models.Transaction(**transaction_data)
                db.add(new_transaction)

                # create a wallet transaction
                wallet_transaction_data = {
                    "amount": expected_amount,
                    "transaction_type": "moved_to_chama",
                    "transaction_date": transaction_date,
                    "transaction_completed": True,
                    "transaction_code": transaction_code,
                    "transaction_destination": member.chama_id,
                    "member_id": member.member_id,
                }

                new_wallet_transaction = models.Wallet_Transaction(
                    **wallet_transaction_data
                )
                db.add(new_wallet_transaction)

                # update the wallet balance
                member_record = (
                    db.query(models.Member)
                    .filter(models.Member.id == member.member_id)
                    .first()
                )
                member_record.wallet_balance = wallet_balance - expected_amount

                # update the chama account balance
                chama_account = (
                    db.query(models.Chama_Account)
                    .filter(models.Chama_Account.chama_id == member.chama_id)
                    .first()
                )

                chama_account.account_balance += expected_amount + total_fines_deducted

            db.commit()

        return {"message": "Auto contribution completed successfully"}
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to auto contribute {e}")
        raise HTTPException(status_code=400, detail="Failed to auto contribute")


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
                func.date(models.Transaction.date_of_transaction)
                > prev_contribution_date.date(),
                func.date(models.Transaction.date_of_transaction)
                <= upcoming_contribution_date.date(),
            )
        )
        .scalar()
    )

    return expected_amount - total_contribution


def generate_transaction_code(transaction_type, origin, destination):
    # Get current month abbreviation in uppercase
    month_prefix = datetime.now(nairobi_tz).strftime("%b").upper()

    # Determine transaction prefix based on transaction type
    if transaction_type.lower() == "deposit":
        prefix = f"{month_prefix}DEPO"
    elif transaction_type.lower() == "withdrawal":
        prefix = f"{month_prefix}DRAW"
    elif transaction_type.lower() == "auto_deposit":
        prefix = f"{month_prefix}ADEP"
    elif transaction_type.lower() == "auto_repay":
        prefix = f"{month_prefix}AREP"
    elif transaction_type.lower() == "fine_repay":
        prefix = f"{month_prefix}FREP"
    elif transaction_type.lower() == "moved_to_wallet":
        prefix = f"{month_prefix}MTOW"
    elif transaction_type.lower() == "deposited_to_wallet":
        prefix = f"{month_prefix}DTOW"
    elif transaction_type.lower() == "withdrawn_from_wallet":
        prefix = f"{month_prefix}WFRW"
    elif transaction_type.lower() == "moved_to_chama":
        prefix = f"{month_prefix}MTCH"
    else:
        raise ValueError("Invalid transaction type. Use 'deposit' or 'withdrawal'.")

    # Generate timestamp
    timestamp = datetime.now(nairobi_tz).strftime("%Y%m%d%H%M%S")

    # Generate random element
    random_element = "".join(
        random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=5)
    )

    # Construct transaction code
    transaction_code = f"{prefix}{timestamp}_{random_element}_{origin}_{destination}"

    return transaction_code


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
            db.query(models.Member.wallet_number)
            .filter(models.Member.id == member_id)
            .scalar()
        )

        return {"wallet_number": wallet_number}
    except Exception as e:
        transaction_error_logger.error(f"Failed to get wallet number {e}")
        raise HTTPException(status_code=400, detail="Failed to get wallet number")


def generateWalletNumber(db, member_id):
    wallet_number = (
        db.query(models.Member.wallet_number)
        .filter(models.Member.id == member_id)
        .scalar()
    )
    return wallet_number
