from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy import func, update, and_, table, column, desc, or_, insert
from sqlalchemy.orm import Session, joinedload, aliased
from typing import Union
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import logging, random, time
from typing import List
from uuid import uuid4

from .date_functions import (
    calculate_custom_interval,
    calculate_monthly_interval,
    calculate_daily_interval,
    calculate_weekly_interval,
    calculate_monthly_same_day_interval,
)

from .. import schemas, database, utils, oauth2, models

from .managers import share_names

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
                    models.WalletTransaction.destination == member.wallet_id,
                    models.WalletTransaction.transaction_completed == True,
                    models.WalletTransaction.transaction_type.in_(
                        ["deposit", "transfer"]
                    ),
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
            .limit(2)
            .all()
        )

        wallet_transfers = (
            db.query(models.WalletTransaction)
            .filter(
                and_(
                    models.WalletTransaction.user_id == current_user.id,
                    models.WalletTransaction.transaction_completed == True,
                    models.WalletTransaction.transaction_type == "transfer",
                    models.WalletTransaction.origin == member.wallet_id,
                )
            )
            .order_by(desc(models.WalletTransaction.transaction_date))
            .limit(2)
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
                "transaction_type": (
                    "Received"
                    if transaction.transaction_type == "transfer"
                    else "Deposited"
                ),
                "transaction_date": transaction.transaction_date.strftime("%d-%B-%Y"),
                "transaction_time": transaction.transaction_date.strftime("%H:%M:%S"),
                "transaction_amount": transaction.amount,
                "transaction_origin": transaction.origin,
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

        wallet_transfers_data = [
            {
                "transaction_type": "Transferred",
                "transaction_date": transaction.transaction_date.strftime("%d-%B-%Y"),
                "transaction_time": transaction.transaction_date.strftime("%H:%M:%S"),
                "transaction_amount": transaction.amount,
                "transaction_destination": transaction.destination,
            }
            for transaction in wallet_transfers
        ]

        return {
            "wallet_id": member.wallet_id,
            "wallet_balance": member.wallet_balance,
            "zetucoins": member.zetucoins,
            "recent_transactions": recent_transactions,
            "wallet_transactions": wallet_transactions_data,
            "sent_transactions": sent_transactions_data,
            "wallet_transfers": wallet_transfers_data,
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
        # TODO: recent transaction will be those done by manager outside of chama and not investment/loan transactions

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
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        # check if today is past the last joining date
        if datetime.now(nairobi_tz).date() < activity.last_joining_date.date():
            raise HTTPException(
                status_code=400,
                detail="You cannot contribute before the last joining date",
            )

        expected_amount = contrib_data.expected_contribution
        amount = contrib_data.amount
        user_id = current_user.id
        transaction_date = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )

        user = db.query(models.User).filter(models.User.id == user_id).first()
        wallet_id = user.wallet_id
        wallet_balance = user.wallet_balance

        print("wallet_id:", wallet_id)
        num_shares = (
            db.query(models.activity_user_association.c.shares)
            .filter(
                and_(
                    models.activity_user_association.c.user_id == user_id,
                    models.activity_user_association.c.activity_id == activity_id,
                )
            )
            .scalar()
        )

        if not num_shares:
            raise HTTPException(status_code=404, detail="User shares not found")

        amount_per_share = int(expected_amount / num_shares)
        activity_fine = activity.fine
        print("amount_per_share:", amount_per_share)
        print("activity_fine:", activity_fine)

        missed_rotations = None
        fines = (
            db.query(models.ActivityFine)
            .filter(
                and_(
                    models.ActivityFine.activity_id == activity_id,
                    models.ActivityFine.user_id == user_id,
                    models.ActivityFine.is_paid == False,
                )
            )
            .order_by(models.ActivityFine.fine_date)
            .all()
        )

        if fines:
            # retrieve the missed rotations correspnding to the fines
            fine_dates = [fine.fine_date for fine in fines]
            print("fine_dates:\n", fine_dates)
            missed_rotations = (
                db.query(models.RotatingContributions)
                .filter(
                    and_(
                        models.RotatingContributions.rotation_date.in_(fine_dates),
                        models.RotatingContributions.contributor_id == user_id,
                        models.RotatingContributions.activity_id == activity_id,
                        models.RotatingContributions.contributed_on_time == False,
                        models.RotatingContributions.contributed_amount + models.RotatingContributions.fine < models.RotatingContributions.expected_amount + activity_fine,
                    )
                )
                .all()
            )

        total_fines_repaid = 0
        total_contribution = 0
        break_outer_loop = False
        print("=========start nested============")
        with db.begin_nested():
            if fines:
                print("===fines===")
                for fine in fines:
                    print("expected_repayment:", fine.expected_repayment, "fine_date:", fine.fine_date)
                    amount_repaid_towards_fine = 0  # amount repaid towards this fine
                    fine_transaction_code = generate_transaction_code(
                        "manual_fine_repayment", wallet_id
                    )
                    # find the missed rotations for this fine
                    missed_rotations_for_fine = [
                        rotation
                        for rotation in missed_rotations
                        if rotation.rotation_date == fine.fine_date
                    ]
                    print("num_rotations:", len(missed_rotations_for_fine))

                    for missed_rotation in missed_rotations_for_fine:
                        print("missed_rotation:", missed_rotation.contributing_share)
                        missed_balance = (
                            missed_rotation.expected_amount
                            - missed_rotation.contributed_amount
                        ) + activity_fine
                        print("missed_balance:", missed_balance)

                        if amount >= missed_balance:
                            print("start_amt:", amount)
                            amount -= missed_balance
                            print("end_amt:", amount)
                            fine_amount_repaid = missed_balance
                            fine.expected_repayment = max(
                                fine.expected_repayment - missed_balance, 0
                            )
                            amount_repaid_towards_fine += missed_balance

                            # update the rotating contribution
                            missed_rotation.contributed_amount += (
                                missed_balance - activity_fine
                            )
                            missed_rotation.fine = activity_fine
                        else:
                            print("else start_amt:", amount)
                            fine.expected_repayment = max(
                                fine.expected_repayment - amount, 0
                            )
                            fine_amount_repaid = amount
                            amount_repaid_towards_fine += amount
                            amount = 0

                            # update the rotating contribution
                            # if the fine_amount_repaid + missed_rotation.contributed amount, then the excess is moved to fine
                            if (
                                fine_amount_repaid + missed_rotation.contributed_amount
                                > missed_rotation.expected_amount
                            ):
                                contribution_amount = (
                                    missed_rotation.expected_amount
                                    - missed_rotation.contributed_amount
                                )
                                fine_amount = fine_amount_repaid - contribution_amount

                                missed_rotation.contributed_amount += (
                                    contribution_amount
                                )
                                missed_rotation.fine += fine_amount
                            else:
                                missed_rotation.contributed_amount += fine_amount_repaid

                        print("fine_amount_repaid:", fine_amount_repaid)
                        total_fines_repaid += fine_amount_repaid
                        # here we will record this transaction for late disbursement
                        late_disbursement_record = {
                            "chama_id": activity.chama_id,
                            "activity_id": activity_id,
                            "late_contributor_id": user_id,
                            "late_recipient_id": missed_rotation.recipient_id,
                            "late_contribution": fine_amount_repaid,
                            "missed_rotation_date": missed_rotation.rotation_date,
                        }
                        # record the late disbursement
                        new_late_disbursement = models.LateRotationDisbursements(
                            **late_disbursement_record
                        )
                        db.add(new_late_disbursement)

                        if amount == 0:
                            print("===amount is 0: breaking===")
                            break_outer_loop = True
                            break

                    # after processing all the missed rotations for this fine, we record the transaction
                    print("amount_repaid_towards_fine:", amount_repaid_towards_fine)
                    if amount_repaid_towards_fine > 0:
                        fine_transaction_data = {
                            "user_id": user_id,
                            "amount": amount_repaid_towards_fine,
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

                    # mark the fine as paid if the amount repaid is equal to the expected repayment
                    if fine.expected_repayment == 0:
                        fine.is_paid = True
                        fine.paid_date = transaction_date

                    # if the amount is 0, we break
                    if break_outer_loop:
                        print("===breaking outer loop===")
                        break

            # if after fine repayment, the member has some amount left, we contribute towards the upcoming rotation_contribution
            print("===amount:", amount)
            if amount > 0 and expected_amount > 0:
                print("======excess: we are now contributing to the next rotation=====")
                transaction_code = generate_transaction_code(
                    "manual_contribution", wallet_id
                )

                # just like with fines/share repayment we will retrieve this users upcoming rotations and contribute to them
                upcoming_rotations = (
                    db.query(models.RotatingContributions)
                    .filter(
                        and_(
                            models.RotatingContributions.contributor_id == user_id,
                            models.RotatingContributions.activity_id == activity_id,
                            models.RotatingContributions.rotation_date
                            == next_contribution_date,
                            models.RotatingContributions.expected_amount
                            != models.RotatingContributions.contributed_amount,
                        )
                    )
                    .all()
                )
                print("num:", len(upcoming_rotations))

                for rotation in upcoming_rotations:
                    print("rotation:", rotation.contributing_share)
                    contributing_bal = (
                        rotation.expected_amount - rotation.contributed_amount
                    )
                    amount_contributed = 0
                    if amount >= contributing_bal:
                        amount -= contributing_bal
                        rotation.contributed_amount += contributing_bal
                        rotation.contributed_on_time = True
                        amount_contributed += contributing_bal
                        print("===amount_contributed:==", amount_contributed)
                    else:
                        rotation.contributed_amount += amount
                        amount_contributed += amount
                        print("===amount_contributed:", amount_contributed)
                        amount = 0

                    # sum the total contribution
                    total_contribution += amount_contributed
                    print("===total_contribution:", total_contribution)

                    if amount == 0:
                        break

                # record the transaction
                if total_contribution > 0:
                    transaction_data = {
                        "user_id": user_id,
                        "amount": total_contribution,
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

            # update the wallet balance
            user_record = (
                db.query(models.User).filter(models.User.id == user_id).with_for_update().first()
            )
            if user_record.wallet_balance < total_contribution + total_fines_repaid:
                raise HTTPException(
                    status_code=400, detail="Insufficient wallet balance"
                )

            user_record.wallet_balance -= total_contribution + total_fines_repaid

            # update the activity account balance
            activity_account = (
                db.query(models.Activity_Account)
                .filter(models.Activity_Account.activity_id == activity_id)
                .with_for_update()
                .first()
            )
            activity_account.account_balance += total_fines_repaid + total_contribution

            # update the chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == activity.chama_id)
                .with_for_update()
                .first()
            )
            chama_account.account_balance += total_fines_repaid + total_contribution

            db.commit()
        return {"message": "Contribution successful"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to contribute to merry go round {e}")
        raise HTTPException(
            status_code=400, detail="Failed to contribute to merry go round"
        )


@router.post(
    "/automated_merry_go_round_contributions", status_code=status.HTTP_201_CREATED
)
async def automatic_merry_go_round_contributions(
    db: Session = Depends(database.get_db),
):
    try:
        print("===start auto contributions====")
        today = datetime.now(nairobi_tz).date()
        print("===today:", today)
        transaction_datetime = datetime.now(nairobi_tz).replace(tzinfo=None)
        # retrieve all merry go round activities whose next contribution date is today and have their id in the activity_contribution_date table activity_id
        # for this we will use two tables, the activity_contribution_date and the auto_contribution
        activities = (
            db.query(models.ActivityContributionDate)
            .join(
                models.AutoContribution,
                models.ActivityContributionDate.activity_id
                == models.AutoContribution.activity_id,
            )
            .filter(
                and_(
                    func.date(models.ActivityContributionDate.next_contribution_date)
                    == today,
                    models.ActivityContributionDate.activity_type == "merry-go-round",
                )
            )
            .all()
        )
        print("activities:", len(activities))

        if not activities:
            print("No merry go round activities today")
            return {"message": "No merry go round activities today"}

        # Process each activity individually
        for activity in activities:
            print("==========activity==========")
            activity_id = activity.activity_id
            print("activity_id:", activity_id)
            chama_id = activity.chama_id
            activity_fine = (
                db.query(models.Activity.fine)
                .filter(models.Activity.id == activity_id)
                .scalar()
            )
            print("activity_fine:", activity_fine)

            # retrieeve auto contributors for the current activity
            activity_users = (
                db.query(
                    models.AutoContribution.user_id,
                    models.AutoContribution.activity_id,
                    models.User.wallet_id,
                    models.User.wallet_balance,
                )
                .join(models.User, models.User.id == models.AutoContribution.user_id)
                .filter(
                    and_(
                        models.AutoContribution.activity_id == activity_id,
                        models.User.wallet_balance > 0,
                    )
                )
                .all()
            )
            print("activity_users:", len(activity_users))

            if not activity_users:
                # no auto contributors for this activity, go to the next activity
                continue

            user_ids = [user.user_id for user in activity_users]
            print("user_ids:", user_ids)

            # retrieve any unpaid fines for the users in the activity
            fines = (
                db.query(models.ActivityFine)
                .filter(
                    and_(
                        models.ActivityFine.user_id.in_(user_ids),
                        models.ActivityFine.activity_id == activity_id,
                        models.ActivityFine.is_paid == False,
                    )
                )
                .order_by(models.ActivityFine.fine_date)
                .all()
            )

            # retrieve missed rotations that match the fines
            fine_dates = [fine.fine_date for fine in fines]
            missed_rotations = (
                db.query(models.RotatingContributions)
                .filter(
                    and_(
                        models.RotatingContributions.contributor_id.in_(user_ids),
                        models.RotatingContributions.rotation_date.in_(fine_dates),
                        models.RotatingContributions.activity_id == activity_id,
                        models.RotatingContributions.contributed_on_time == False,
                        models.RotatingContributions.contributed_amount + models.RotatingContributions.fine < models.RotatingContributions.expected_amount + activity_fine,
                    )
                )
                .all()
            )

            # loop through each user within the activty and process contributions and fines
            for user in activity_users:
                print("==========user==========")
                user_id = user.user_id
                wallet_id = user.wallet_id
                wallet_balance = user.wallet_balance
                print("user_id:", user_id)
                print("wallet_bal:", wallet_balance)
                total_fines_repaid = 0
                total_contribution = 0
                break_outer_loop = False

                # start nested transaction to handle fines and contributions for each user
                with db.begin_nested():
                    # process fines
                    user_fines = [fine for fine in fines if fine.user_id == user_id]
                    if user_fines:
                        for fine in user_fines:
                            missed_rotations_for_fine = [
                                rotation
                                for rotation in missed_rotations
                                if rotation.rotation_date == fine.fine_date
                                and rotation.contributor_id == user_id
                                and rotation.activity_id == activity_id
                            ]

                            for missed_rotation in missed_rotations_for_fine:
                                deducted = 0
                                unpaid_fine = activity_fine - missed_rotation.fine
                                missed_balance = unpaid_fine + (
                                    missed_rotation.expected_amount
                                    - missed_rotation.contributed_amount
                                )

                                if wallet_balance >= missed_balance:
                                    print("wallet_bal:", wallet_balance)
                                    wallet_balance -= missed_balance
                                    fine.expected_repayment = max(
                                        fine.expected_repayment - missed_balance, 0
                                    )
                                    missed_rotation.contributed_amount += (
                                        missed_balance - unpaid_fine
                                    )
                                    missed_rotation.fine += unpaid_fine
                                    deducted += missed_balance
                                elif (
                                    wallet_balance < missed_balance
                                    and wallet_balance > 0
                                ):
                                    fine.expected_repayment = max(
                                        fine.expected_repayment - wallet_balance, 0
                                    )

                                    if (
                                        wallet_balance
                                        > missed_rotation.expected_amount
                                        - missed_rotation.contributed_amount
                                    ):
                                        contribution_amount = (
                                            missed_rotation.expected_amount
                                            - missed_rotation.contributed_amount
                                        )
                                        fine_amount = (
                                            wallet_balance - contribution_amount
                                        )

                                        missed_rotation.contributed_amount += (
                                            contribution_amount
                                        )
                                        missed_rotation.fine += fine_amount
                                    else:
                                        missed_rotation.contributed_amount += (
                                            wallet_balance
                                        )

                                    deducted += wallet_balance
                                    wallet_balance = 0

                                total_fines_repaid += deducted
                                print("total_fines_repaid:", total_fines_repaid)

                                # record late disbursement record
                                late_disbursement_record = {
                                    "chama_id": chama_id,
                                    "activity_id": activity_id,
                                    "late_contributor_id": user_id,
                                    "late_recipient_id": missed_rotation.recipient_id,
                                    "late_contribution": deducted,
                                    "missed_rotation_date": missed_rotation.rotation_date,
                                }
                                db.add(
                                    models.LateRotationDisbursements(
                                        **late_disbursement_record
                                    )
                                )

                                if wallet_balance == 0:
                                    print("===wallet 0 =====")
                                    break_outer_loop = True
                                    break

                            # mark the fine as paid if the expected repayment is 0
                            if fine.expected_repayment == 0:
                                fine.is_paid = True
                                fine.paid_date = transaction_datetime

                            if break_outer_loop:
                                print("===break_outer_loop====")
                                break

                        # record the fine repayment transaction
                        if total_fines_repaid > 0:
                            print("======recording fines======")
                            fine_transaction_code = generate_transaction_code(
                                "auto_late_contribution", wallet_id
                            )
                            fine_transaction_data = {
                                "user_id": user_id,
                                "amount": total_fines_repaid,
                                "origin": wallet_id,
                                "activity_id": activity_id,
                                "transaction_date": transaction_datetime,
                                "updated_at": transaction_datetime,
                                "transaction_completed": True,
                                "transaction_code": fine_transaction_code,
                                "transaction_type": "late contribution",
                            }
                            db.add(models.ActivityTransaction(**fine_transaction_data))

                    # process contributions
                    if wallet_balance > 0:
                        print("===wallet_balance > 0====")
                        next_contributions = (
                            db.query(models.RotatingContributions)
                            .filter(
                                and_(
                                    models.RotatingContributions.contributor_id
                                    == user_id,
                                    models.RotatingContributions.activity_id
                                    == activity_id,
                                    func.date(
                                        models.RotatingContributions.rotation_date
                                    )
                                    == today,
                                    models.RotatingContributions.expected_amount
                                    != models.RotatingContributions.contributed_amount,
                                )
                            )
                            .all()
                        )

                        for rotation in next_contributions:
                            print("====we have conts=====")
                            contributing_balance = (
                                rotation.expected_amount - rotation.contributed_amount
                            )
                            amount_contributed = 0

                            if wallet_balance >= contributing_balance:
                                wallet_balance -= contributing_balance
                                rotation.contributed_amount += contributing_balance
                                rotation.contributed_on_time = True
                                amount_contributed += contributing_balance
                            elif (
                                wallet_balance < contributing_balance
                                and wallet_balance > 0
                            ):
                                rotation.contributed_amount += wallet_balance
                                amount_contributed += wallet_balance
                                wallet_balance = 0

                            total_contribution += amount_contributed
                            print("total_contribution:", total_contribution)

                            if wallet_balance == 0:
                                break

                        if total_contribution > 0:
                            print("r===record trans=====")
                            # record the transaction
                            transaction_code = generate_transaction_code(
                                "auto_contribution", wallet_id
                            )
                            transaction_data = {
                                "user_id": user_id,
                                "amount": total_contribution,
                                "origin": wallet_id,
                                "activity_id": activity_id,
                                "transaction_date": transaction_datetime,
                                "updated_at": transaction_datetime,
                                "transaction_completed": True,
                                "transaction_code": transaction_code,
                                "transaction_type": "contribution",
                            }
                            db.add(models.ActivityTransaction(**transaction_data))

                    # update the wallet balance
                    if total_contribution + total_fines_repaid > 0:
                        print("=====update wallet bal====")
                        user_record = (
                            db.query(models.User)
                            .filter(models.User.id == user_id)
                            .with_for_update()
                            .first()
                        )
                        if not user_record:
                            db.rollback()
                            continue

                        print("wallet_balance==:", user_record.wallet_balance)
                        if (
                            user_record.wallet_balance
                            < total_contribution + total_fines_repaid
                        ):
                            db.rollback()
                            continue
                        user_record.wallet_balance -= (
                            total_contribution + total_fines_repaid
                        )

                        print("====updating activity account====")
                        # update the activity account balance
                        activity_account = (
                            db.query(models.Activity_Account)
                            .filter(models.Activity_Account.activity_id == activity_id)
                            .with_for_update()
                            .first()
                        )
                        activity_account.account_balance += (
                            total_contribution + total_fines_repaid
                        )

                        # update the chama account balance
                        chama_account = (
                            db.query(models.Chama_Account)
                            .filter(models.Chama_Account.chama_id == chama_id)
                            .with_for_update()
                            .first()
                        )
                        chama_account.account_balance += (
                            total_contribution + total_fines_repaid
                        )

                db.commit()  # commit the nested transaction for each user
        return {"message": "Automated merry go round contributions successful"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to contribute to merry go round {e}")


"""
@router.post(
    "/automated_merry_go_round_contributions", status_code=status.HTTP_201_CREATED
)
async def automatic_merry_go_round_contributions(
    db: Session = Depends(database.get_db),
):
    try:
        today = datetime.now(nairobi_tz).date()
        transaction_datetime = datetime.now(nairobi_tz).replace(tzinfo=None)

        # retrieve all merry-go-round activities whose next contribution date is today
        activities = (
            db.query(models.ActivityContributionDate)
            .filter(
                and_(
                    func.date(models.ActivityContributionDate.next_contribution_date)
                    == today,
                    models.ActivityContributionDate.activity_type == "merry-go-round",
                )
            )
            .all()
        )
        merry_activity_ids = [activity.activity_id for activity in activities]
        print("merry_activity_ids:", merry_activity_ids)
        if not merry_activity_ids:
            return {"message": "No merry-go-round activities today"}

        # retrieve all auto contributors for the activities above
        activities_users = (
            db.query(
                models.AutoContribution.user_id,
                models.AutoContribution.activity_id,
                models.User.wallet_id,
                models.User.wallet_balance,
            )
            .join(
                models.User,
                models.User.id == models.AutoContribution.user_id,
            )
            .filter(models.AutoContribution.activity_id.in_(merry_activity_ids))
            .all()
        )

        if not activities_users:
            return {"message": "No auto contributors for today"}

        print("activities_users:", activities_users)

        user_ids = [user.user_id for user in activities_users]
        print("user_ids:", user_ids)
        activity_ids = list(set([user.activity_id for user in activities_users]))
        print("activity_ids:", activity_ids)

        # retrieve user shares and relevant
        user_shares = (
            db.query(models.RotatingContributions)
            .filter(
                and_(
                    models.RotatingContributions.contributor_id.in_(user_ids),
                    func.date(models.RotatingContributions.rotation_date) == today,
                    models.RotatingContributions.activity_id.in_(activity_ids),
                )
            )
            .all()
        )

        # retrieve any unpaid fines for the users in the activities
        fines = (
            db.query(models.ActivityFine)
            .filter(
                and_(
                    models.ActivityFine.user_id.in_(user_ids),
                    models.ActivityFine.activity_id.in_(activity_ids),
                    models.ActivityFine.is_paid == False,
                )
            )
            .order_by(models.ActivityFine.fine_date)
            .all()
        )

        # retrieve missed rotations that match the fines
        fine_dates = [fine.fine_date for fine in fines]
        print("fine_dates:\n", fine_dates)
        missed_rotations = (
            db.query(models.RotatingContributions)
            .filter(
                and_(
                    models.RotatingContributions.contributor_id.in_(user_ids),
                    models.RotatingContributions.activity_id.in_(activity_ids),
                    func.date(models.RotatingContributions.rotation_date).in_(
                        fine_dates
                    ),
                    # might have to add more filters here
                )
            )
            .all()
        )

        # loop through each user and process contributions and fines
        for user in activities_users:
            print("===user count====")
            user_id = user.user_id
            print("user_id:", user_id)
            print("activity_id:", user.activity_id)
            wallet_id = user.wallet_id
            wallet_balance = user.wallet_balance
            total_fines_repaid = 0
            total_contribution = 0
            break_outer_loop = False

            my_fines = (
                db.query(models.ActivityFine)
                .filter(
                    and_(
                        models.ActivityFine.user_id == user_id,
                        models.ActivityFine.activity_id == user.activity_id,
                        models.ActivityFine.is_paid == False,
                    )
                )
                .all()
            )
            print("my_fines:", my_fines)

            # start a nested transaction to handle the fines and contributions
            with db.begin_nested():
                # process fines
                user_fines = [fine for fine in fines if fine.user_id == user_id]
                print("fines", user_fines)
                print("fines", len(user_fines))
                if user_fines:
                    for fine in user_fines:
                        fine_amount_repaid = 0  # amount repaid towards this fine

                        # find the missed rotations for this fine
                        missed_rotations_for_fine = [
                            rotation
                            for rotation in missed_rotations
                            if rotation.rotation_date == fine.fine_date
                            and rotation.contributor_id == user_id
                            and rotation.activity_id == user.activity_id
                        ]
                        print(
                            "missed_rotations_for_fine:", len(missed_rotations_for_fine)
                        )
                        for missed_rotation in missed_rotations_for_fine:
                            print(
                                "missed_rotation:", missed_rotation.contributing_share
                            )

                        # loop through the missed rotations and repay the fine and missed contribution
                        for missed_rotation in missed_rotations_for_fine:
                            missed_balance = fine.fine + (
                                missed_rotation.expected_amount
                                - missed_rotation.contributed_amount
                            )
                            print("missed_balance:", missed_balance)
                            print("wallet_balance:", wallet_balance)

                            # if the user has enough balance to repay the missed rotation
                            if wallet_balance >= missed_balance:
                                print("greater balance")
                                wallet_balance -= missed_balance
                                fine_amount_repaid += missed_balance
                                print("fine_exp_1:", fine.expected_repayment)
                                fine.expected_repayment = max(
                                    fine.expected_repayment - missed_balance, 0
                                )
                                print("fine_exp_2:", fine.expected_repayment)
                                missed_rotation.contributed_amount += (
                                    missed_balance - fine.fine
                                )
                                missed_rotation.fine = fine.fine
                            else:
                                print("lesser balance")
                                # if the user has a partial balance to repay the missed rotation
                                fine.expected_repayment = max(
                                    fine.expected_repayment - wallet_balance, 0
                                )
                                fine_amount_repaid += wallet_balance
                                wallet_balance = 0
                                if (
                                    fine_amount_repaid
                                    + missed_rotation.contributed_amount
                                    > missed_rotation.expected_amount
                                ):
                                    contribution_amount = (
                                        missed_rotation.expected_amount
                                        - missed_rotation.contributed_amount
                                    )
                                    fine_amount = (
                                        fine_amount_repaid - contribution_amount
                                    )
                                    missed_rotation.contributed_amount += (
                                        contribution_amount
                                    )
                                    missed_rotation.fine += fine_amount
                                else:
                                    missed_rotation.contributed_amount += (
                                        fine_amount_repaid
                                    )

                            # record the total fines repaid
                            print("fine_amount_repaid:", fine_amount_repaid)
                            total_fines_repaid += fine_amount_repaid
                            print("total_fines_repaid:", total_fines_repaid)

                            chama_id = (
                                db.query(models.Activity.chama_id)
                                .filter(models.Activity.id == user.activity_id)
                                .scalar()
                            )

                            # record the late disbursement
                            late_disbursement_record = {
                                "chama_id": chama_id,
                                "activity_id": user.activity_id,
                                "late_contributor_id": user_id,
                                "late_recipient_id": missed_rotation.recipient_id,
                                "late_contribution": fine_amount_repaid,
                                "missed_rotation_date": missed_rotation.rotation_date,
                            }
                            new_late_disbursement = models.LateRotationDisbursements(
                                **late_disbursement_record
                            )
                            db.add(new_late_disbursement)

                            # if the available amount is zero, stop processing the fines
                            if wallet_balance == 0:
                                break_outer_loop = True
                                break

                        print("===record fine====")
                        # record the transaction
                        fine_transaction_code = generate_transaction_code(
                            "auto_late_contribution", wallet_id
                        )
                        fine_transaction_data = {
                            "user_id": user_id,
                            "amount": fine_amount_repaid,
                            "origin": wallet_id,
                            "activity_id": user.activity_id,
                            "transaction_date": transaction_datetime,
                            "updated_at": transaction_datetime,
                            "transaction_completed": True,
                            "transaction_code": fine_transaction_code,
                            "transaction_type": "late contribution",
                        }
                        new_fine_transaction = models.ActivityTransaction(
                            **fine_transaction_data
                        )
                        db.add(new_fine_transaction)

                        # mark the fine as paid if its fully repaid
                        if fine.expected_repayment == 0:
                            fine.is_paid = True
                            fine.paid_date = transaction_datetime

                        if break_outer_loop:
                            print("====breaking===")
                            break

                # if the user has some balance left, contribute towards the upcoming rotation
                if wallet_balance > 0:
                    print("=== contribution====")
                    # find thee upcoming rotation contribution
                    next_contributions = (
                        db.query(models.RotatingContributions)
                        .filter(
                            and_(
                                models.RotatingContributions.contributor_id == user_id,
                                models.RotatingContributions.activity_id
                                == user.activity_id,
                                func.date(models.RotatingContributions.rotation_date)
                                == today,
                                models.RotatingContributions.expected_amount
                                != models.RotatingContributions.contributed_amount,
                            )
                        )
                        .all()
                    )
                    print("next_contributions:", next_contributions)

                    # contribute the remaining amount towards the next rotation
                    if next_contributions:
                        print("====we have next cont====")
                        for rotation in next_contributions:
                            print("rotation share:", rotation.contributing_share)
                            contribution_balance = (
                                rotation.expected_amount - rotation.contributed_amount
                            )
                            if wallet_balance >= contribution_balance:
                                rotation.contributed_amount += contribution_balance
                                wallet_balance -= contribution_balance
                                total_contribution += contribution_balance
                            else:
                                rotation.contributed_amount += wallet_balance
                                total_contribution += wallet_balance
                                wallet_balance = 0
                                break

                            print("total_contribution:", total_contribution)

                        if total_contribution > 0:
                            # record the contribution transaction
                            print("===record contribution====")
                            contribution_transaction_data = {
                                "user_id": user_id,
                                "amount": total_contribution,
                                "origin": wallet_id,
                                "activity_id": user.activity_id,
                                "transaction_date": transaction_datetime,
                                "updated_at": transaction_datetime,
                                "transaction_completed": True,
                                "transaction_code": generate_transaction_code(
                                    "auto_contribution", wallet_id
                                ),
                                "transaction_type": "contribution",
                            }
                            new_contribution_transaction = models.ActivityTransaction(
                                **contribution_transaction_data
                            )
                            db.add(new_contribution_transaction)

                # update the wallet balance after processing fines and contributions
                if total_contribution + total_fines_repaid > 0:
                    print("===update wallet balance====")
                    user_record = (
                        db.query(models.User)
                        .filter(models.User.id == user_id)
                        .with_for_update()
                        .first()
                    )
                    if (
                        user_record.wallet_balance
                        < total_contribution + total_fines_repaid
                    ):
                        print("===insufficient balance===")
                        # we will skip this user and log the error but continue processing the rest
                        transaction_error_logger.error("Insufficient wallet balance")
                        db.rollback()
                        continue

                    user_record.wallet_balance -= (
                        total_contribution + total_fines_repaid
                    )

                    # update the activity account balance and chama account balance
                    print("===update acct balances====")
                    activity_account = (
                        db.query(models.Activity_Account)
                        .filter(models.Activity_Account.activity_id == user.activity_id)
                        .with_for_update()
                        .first()
                    )
                    activity_account.account_balance += (
                        total_fines_repaid + total_contribution
                    )
                    print("activity_account:", activity_account.account_balance)
                    print("user.activity_id:", user.activity_id)

                    # retrieve chama_id for this activity
                    chama_id = (
                        db.query(models.Activity.chama_id)
                        .filter(models.Activity.id == user.activity_id)
                        .scalar()
                    )
                    print("chama_id:", chama_id)

                    chama_account = (
                        db.query(models.Chama_Account)
                        .filter(models.Chama_Account.chama_id == chama_id)
                        .with_for_update()
                        .first()
                    )
                    chama_account.account_balance += (
                        total_fines_repaid + total_contribution
                    )

                db.commit()  # commit the nested transaction for each user
        return {"message": "Automated merry-go-round contributions successful"}
    except HTTPException as http_exc:
        transaction_error_logger.error(
            f"Failed to automate merry go round contributions {http_exc}"
        )
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(
            f"Failed to automate merry go round contributions {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to automate merry go round contributions"
        )
"""


# contribute t the generic activities
@router.post(
    "/contribute/generic/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def contribute_to_generic_activity(
    activity_id: int,
    contrib_data: schemas.ContributeToActivityBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        # ensure its past the last day of joining before contributing
        if datetime.now(nairobi_tz).date() < activity.last_joining_date.date():
            raise HTTPException(
                status_code=400,
                detail="You cannot contribute before the last joining date",
            )

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

            if user_record.wallet_balance < total_fines_repaid + amount_contributed:
                raise HTTPException(
                    status_code=400, detail="Insufficient wallet balance"
                )

            user_record.wallet_balance -= amount_contributed + total_fines_repaid

            activity = (
                db.query(models.Activity)
                .filter(models.Activity.id == activity_id)
                .first()
            )

            if not activity:
                raise HTTPException(status_code=404, detail="Activity not found")

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
        return {"message": "Contribution successful"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to contribute to activity{e}")
        raise HTTPException(status_code=400, detail="Failed to contribute to activity")


# generate transaction code
def generate_transaction_code(transaction_type, destination):
    # define a prefix for each transaction
    prefixes = {
        "transfer": "TR",
        "auto_contribution": "AC",
        "auto_late_contribution": "ALC",
        "manual_contribution": "MC",
        "manual_fine_repayment": "MFR",
        "unprocessed wallet deposit": "UWD",
        "unprocessed registration fee": "URF",
        "unprocessed wallet withdrawal": "UWW",
        "share increase adjustment cost": "SIAC",
    }

    # get the current timestamp - date - month - year - hour - minute - second
    timestamp = datetime.now(nairobi_tz).strftime("%d%m%Y%H%M%S")
    # generate a random 4-digit number to ensure uniqueness
    unique_number = random.randint(1000, 9999)

    # get the prefix for the transaction type
    # for unknown transaction types, use UNX
    prefix = prefixes.get(transaction_type, "UNX")

    # create the transaction code
    transaction_code = f"{prefix}_{destination}-{timestamp}-{unique_number}"
    return transaction_code


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
# The activities in this route will exclude merry-go-round activities
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
                models.Activity.activity_type,
            )
            .join(models.User, models.User.id == models.AutoContribution.user_id)
            .join(
                models.Activity,
                models.Activity.id == models.AutoContribution.activity_id,
            )
            .filter(
                and_(
                    func.date(models.AutoContribution.next_contribution_date) == today,
                    models.User.wallet_balance > 0,
                    models.Activity.activity_type != "merry-go-round",
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


# retrieving members rotation_contribution pahe data
@router.get(
    "/rotation_contributions/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_activity_rotation_contribution(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        user_in_activity = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_id == current_user.id,
                )
            )
            .first()
        )
        if not user_in_activity:
            raise HTTPException(
                status_code=404, detail="You are not a member of this activity"
            )

        upcoming_rotation_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )
        rotation_date = upcoming_rotation_date.strftime("%Y-%B-%d")

        if not upcoming_rotation_date:
            raise HTTPException(
                status_code=404, detail="Upcoming rotation date not found"
            )

        pooled_so_far = (
            db.query(
                func.coalesce(
                    func.sum(models.RotatingContributions.contributed_amount), 0
                )
            )
            .filter(
                and_(
                    models.RotatingContributions.activity_id == activity_id,
                    models.RotatingContributions.rotation_date
                    == upcoming_rotation_date,
                )
            )
            .scalar()
        )

        # print("upcoming rotation date", upcoming_rotation_date)

        # check if this activity has a rotation_order record
        rotation_order = db.query(models.RotationOrder).filter(
            and_(
                models.RotationOrder.activity_id == activity_id,
            )
        )
        if rotation_order:
            rotation_order = True
        else:
            rotation_order = False

        cycle_number = (
            db.query(func.coalesce(func.max(models.RotationOrder.cycle_number), 0))
            .filter(models.RotationOrder.activity_id == activity_id)
            .scalar()
        )

        if not cycle_number:
            cycle_number = 0

        upcoming_recipient = (
            db.query(
                models.RotationOrder,
                models.User.first_name,
                models.User.last_name,
                models.User.profile_picture,
            )
            .join(models.User, models.User.id == models.RotationOrder.recipient_id)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.receiving_date == upcoming_rotation_date,
                    # models.RotationOrder.fulfilled == False,
                )
            )
            .first()
        )

        # print("===upcoming recipient===\n")

        if not upcoming_recipient:
            return {
                "pooled_so_far": pooled_so_far,
                "rotation_order": rotation_order,
                "upcoming_rotation_date": rotation_date,
                "upcoming_recipient": None,
                "rotation_contributions": None,
                "received_rotations": None,
            }

        upcoming_recipient_resp = {
            "recipient_name": f"{upcoming_recipient.first_name} {upcoming_recipient.last_name}",
            "profile_picture": upcoming_recipient.profile_picture,
            "cycle_number": upcoming_recipient.RotationOrder.cycle_number,
            "share_name": upcoming_recipient.RotationOrder.share_name,
            "expected_amount": upcoming_recipient.RotationOrder.expected_amount,
            "received_amount": upcoming_recipient.RotationOrder.received_amount,
            "order_in_rotation": upcoming_recipient.RotationOrder.order_in_rotation,
        }
        # print("p====past recipient=====\n", upcoming_recipient_resp)
        # TODO: remember to swap back to having received amount instead of pool calculation - this will also need to reconfigure merry-go-round contributions

        rotation_contributions = (
            db.query(
                models.RotatingContributions,
                models.User.first_name,
                models.User.last_name,
            )
            .join(
                models.User,
                models.User.id == models.RotatingContributions.contributor_id,
            )
            .filter(
                and_(
                    models.RotatingContributions.activity_id == activity_id,
                    models.RotatingContributions.rotation_date
                    == upcoming_rotation_date,
                )
            )
            .all()
        )
        # print("====rotation contributions==\n", rotation_contributions)

        if not rotation_contributions:
            return {
                "pooled_so_far": pooled_so_far,
                "rotation_order": rotation_order,
                "upcoming_rotation_date": rotation_date,
                "upcoming_recipient": upcoming_recipient_resp,
                "rotation_contributions": None,
                "received_rotations": None,
            }

        rotation_contributions_resp = [
            {
                "contributor_name": f"{contribution.first_name} {contribution.last_name}",
                "expected_amount": contribution.RotatingContributions.expected_amount,
                "contributed_amount": contribution.RotatingContributions.contributed_amount,
                "fine": contribution.RotatingContributions.fine,
                "rotation_date": contribution.RotatingContributions.rotation_date,
                "cycle_number": contribution.RotatingContributions.cycle_number,
                "contributing_share": contribution.RotatingContributions.contributing_share,
                "recipient_share": contribution.RotatingContributions.recipient_share,
            }
            for contribution in rotation_contributions
        ]

        # print("===past roations\n", rotation_contributions_resp)
        # now retrieve past rotation receivers from RotationOrder table
        received_rotations = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                )
            )
            .all()
        )

        if not received_rotations:
            return {
                "pooled_so_far": pooled_so_far,
                "rotation_order": rotation_order,
                "upcoming_rotation_date": rotation_date,
                "upcoming_recipient": upcoming_recipient_resp,
                "rotation_contributions": rotation_contributions_resp,
                "received_rotations": None,
            }

        received_rotations_resp = [
            {
                "receiver_name": rotation.user_name,
                "receiving_share_name": rotation.share_name,
                "receiver_amount": rotation.received_amount,
                "receiver_order_in_rotation": rotation.order_in_rotation,
                "cycle_number": rotation.cycle_number,
                "status": "received" if rotation.fulfilled else "not received",
            }
            for rotation in received_rotations
        ]

        return {
            "pooled_so_far": pooled_so_far,
            "rotation_order": rotation_order,
            "upcoming_rotation_date": rotation_date,
            "upcoming_recipient": upcoming_recipient_resp,
            "rotation_contributions": rotation_contributions_resp,
            "received_rotations": received_rotations_resp,
        }
    except Exception as e:
        transaction_error_logger.error(f"Failed to get rotation contribution {e}")
        raise HTTPException(
            status_code=400, detail="Failed to get rotation contribution"
        )


# share increase page data 
# current user share no, the share price, number of past rotations till now, 
@router.get(
    "/share_increase_data/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def share_increase_data(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        today = datetime.now(nairobi_tz).date()
        activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        user_in_activity = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_id == current_user.id,
                )
            )
            .first()
        )

        if not user_in_activity:
            raise HTTPException(
                status_code=404, detail="You are not a member of this activity"
            )

        # get the user share in this activity
        user_share = user_in_activity.shares
        share_value = activity.activity_amount

        # get the share increase activation record from MerryGoRoundShareIncrease
        activation_record = (db.query(models.MerryGoRoundShareIncrease)
        .filter(
            and_(
                models.MerryGoRoundShareIncrease.activity_id == activity_id,
                models.MerryGoRoundShareIncrease.allow_share_increase == True,
                func.date(models.MerryGoRoundShareIncrease.deadline) >= today,
            )
        )
        .first()
        )

        if not activation_record:
            return {
                "share_increase_activated": False,
            }


        # get cycle number
        cycle_number = (
            db.query(func.coalesce(func.max(models.RotationOrder.cycle_number), 0))
            .filter(models.RotationOrder.activity_id == activity_id)
            .scalar()
        )

        # upcoming rotation date/next contribution date
        upcoming_rotation_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )

        # count the number of past rotations till now in our current cycle number
        past_rotations = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                    func.date(models.RotationOrder.receiving_date) < today,
                )
            )
            .count()
        )

        print("===past rotations===", past_rotations)

        return {
            "current_shares": user_share,
            "max_shares": activation_record.max_shares,
            "adjustment_fee": activation_record.adjustment_fee,
            "share_value": share_value,
            "past_rotations": past_rotations,
            "share_increase_activated": True,
            "upcoming_rotation_date": upcoming_rotation_date.strftime("%Y-%B-%d"),
        }
    except HTTPException as http_exc:
        transaction_error_logger.error(f"Failed to get share increase page data {http_exc}")
        raise http_exc
    except Exception as exc:
        transaction_error_logger.error(f"Failed to get share increase page data {exc}")
        raise HTTPException(
            status_code=400, detail="Failed to get share increase page data"
        )


# adjust rotation order by adding a share to a user, adding a rotating contribution and updating the expected amount
# updating activity_user_share_association table for the user

@router.post(
    "/increase_shares/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def increase_merry_go_round_shares(
    activity_id: int,
    no_of_shares: schemas.merryGoRoundShareIncreaseReq = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).date()
        transaction_datetime = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        user_in_activity = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_id == current_user.id,
                )
            )
            # check if acquiring a lock is needed here
            .first()
        )

        if not user_in_activity:
            raise HTTPException(
                status_code=404, detail="User not found in this activity"
            )

        # share increase activation data
        activation_record = (db.query(models.MerryGoRoundShareIncrease)
        .filter(
            and_(
                models.MerryGoRoundShareIncrease.activity_id == activity_id,
                models.MerryGoRoundShareIncrease.allow_share_increase == True,
                func.date(models.MerryGoRoundShareIncrease.deadline) >= today,
            )
        )
        .first()
        )

        if not activation_record:
            raise HTTPException(
                status_code=404, detail="Share increase not activated or deadline passed"
            )

        if user_in_activity.shares + no_of_shares.new_shares > activation_record.max_shares:
            raise HTTPException(
                status_code=404, detail="New shares exceed the maximum allowed shares"
            )

        # calculate adjustment cost and validate wallet balance
        cycle_number = (
            db.query(func.coalesce(func.max(models.RotationOrder.cycle_number), 0))
            .filter(models.RotationOrder.activity_id == activity_id)
            .scalar()
        )

        if cycle_number != activation_record.cycle_number:
            raise HTTPException(
                status_code=400, detail="Invalid cycle number, try again later"
            )

        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )

        # retrieve all rotations in the current cycle upto the next contribution date
        rotations_to_clear = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                    models.RotationOrder.receiving_date <= next_contribution_date,
                )
            )
            .all()
        )

        if not rotations_to_clear:
            # this is okay since we are getting upto the next contribution date
            raise HTTPException(
                status_code=404, detail="No rotations to clear for this cycle"
            )

        # adjustment amount needed
        activity_amount = activity.activity_amount
        adjustment_fee = activation_record.adjustment_fee
        all_rotations_coverage = (len(rotations_to_clear) * activity_amount) * no_of_shares.new_shares
        adjustment_cost = all_rotations_coverage + adjustment_fee

        user_record = db.query(models.User).filter(models.User.id == current_user.id).with_for_update().first()
        if user_record.wallet_balance < adjustment_cost:
            raise HTTPException(
                status_code=400, detail="Insufficient wallet balance for adjustment, top up and try again"
            )

        with db.begin_nested():
            # update the user shares in the activity_user_association table
            new_shares = no_of_shares.new_shares
            current_no_of_shares = user_in_activity.shares
            updated_shares = current_no_of_shares + new_shares

            # update the activity_user_association table
            db.query(models.activity_user_association).filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_id == current_user.id,
                )
            ).update({"shares": updated_shares})

            # add a rotation order record by first getting the last record in the current cycle
            last_rotation = (
                db.query(models.RotationOrder)
                .filter(
                    and_(
                        models.RotationOrder.activity_id == activity_id,
                        models.RotationOrder.cycle_number == cycle_number,
                    )
                )
                .order_by(desc(models.RotationOrder.order_in_rotation))
                .first()
            )

            if not last_rotation:
                raise HTTPException(
                    status_code=404, detail="No last rotation found"
                )

            # insert new records to the rotation order, users may have more than one new share, they will be added as consecutive records
            new_rotations = []
            newly_expected_amount = last_rotation.expected_amount + (activity_amount * new_shares)
            next_receiving_date = None
            frequency = activity.frequency
            interval = activity.interval
            contribution_day = activity.contribution_day
            last_receiving_date = last_rotation.receiving_date

            for i in range(new_shares):
                if frequency == "daily":
                    next_receiving_date = calculate_daily_interval(last_receiving_date)
                elif frequency == "weekly":
                    next_receiving_date = calculate_weekly_interval(last_receiving_date)
                elif frequency == "monthly" and interval in ["first", "second", "third", "fourth", "last"]:
                    next_receiving_date = calculate_monthly_interval(last_receiving_date, interval, contribution_day)
                elif frequency == "monthly" and interval == "monthly":
                    next_receiving_date = calculate_monthly_same_day_interval(last_receiving_date, int(contribution_day))
                elif frequency == "interval" and interval == "custom":
                    next_receiving_date = calculate_custom_interval(last_receiving_date, int(contribution_day))
                
                new_rotation = {
                    "user_name": f"{current_user.first_name} {current_user.last_name}",
                    "chama_id": activity.chama_id,
                    "activity_id": activity_id,
                    "recipient_id": current_user.id,
                    "share_value": activity_amount,
                    "receiving_date": next_receiving_date,
                    "expected_amount": newly_expected_amount,
                    "received_amount": 0,
                    "fulfilled": False,
                    "order_in_rotation": last_rotation.order_in_rotation + i + 1,
                    "share_name": share_names[current_no_of_shares + i],
                    "cycle_number": cycle_number,
                }

                last_receiving_date = next_receiving_date

                new_rotations.append(models.RotationOrder(**new_rotation))

            # add  rotating contribution records for the new shares individually towards the next_contribution_date
            # we accounted for this in the adjustment_cost it will be like they have just contributed towards the upcoming contribution
            upcoming_recipient = (
                db.query(models.RotationOrder)
                .filter(
                    and_(
                        models.RotationOrder.activity_id == activity_id,
                        models.RotationOrder.cycle_number == cycle_number,
                        models.RotationOrder.receiving_date == next_contribution_date,
                    )
                )
                .first()
            )

            new_rotating_contributions = []
            for rotation in new_rotations:
                new_contribution = {
                    "chama_id": activity.chama_id,
                    "activity_id": activity_id,
                    "contributor_id": current_user.id,
                    "recipient_id": upcoming_recipient.recipient_id,
                    "expected_amount": activity_amount,
                    "contributed_amount": activity_amount,
                    "fine": 0,
                    "rotation_date": next_contribution_date,
                    "cycle_number": cycle_number,
                    "contributing_share": rotation.share_name,
                    "recipient_share": upcoming_recipient.share_name,
                    "contributed_on_time": True,
                }

                new_rotating_contributions.append(models.RotatingContributions(**new_contribution))

            # for this upcoming contribution to take effect we have to add a contribution record in the activities transactions table
            transaction_code = generate_transaction_code("contribution", user_record.wallet_id)
            contribution_record = models.ActivityTransaction(
                user_id=current_user.id,
                amount=activity_amount * new_shares,
                origin=user_record.wallet_id,
                activity_id=activity_id,
                transaction_date=transaction_datetime,
                updated_at=transaction_datetime,
                transaction_completed=True,
                transaction_code=transaction_code,
                transaction_type="contribution",
            )
            db.add(contribution_record)

            # use the past rotations we got earlier excluding the upcoming rotation to now make new late disbursement records
            # since we have collected the missed amount this far and for the upcoming contribution day, we can now make sure the
            # recipients of the past rotations receive their share. the upcoming one has already been accounted for in the new rotating contributions
            late_disbursements = []

            for late_recipient in rotations_to_clear:
                if late_recipient.receiving_date == next_contribution_date:
                    continue

                late_disbursement = {
                    "chama_id": activity.chama_id,
                    "activity_id": activity_id,
                    "late_contribution": new_shares * activity_amount,
                    "missed_rotation_date": late_recipient.receiving_date,
                    "disbursement_completed": False,
                    "late_contributor_id": current_user.id,
                    "late_recipient_id": late_recipient.recipient_id,
                }

                late_disbursements.append(models.LateRotationDisbursements(**late_disbursement))

            # now update all rotation order in the currect cycle their new expected amount since we just added new shares
            # first - lock them to avoid race conditions
            rows_to_update = db.query(models.RotationOrder).filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                )
            ).with_for_update().all()
            
            # perform the update
            for row in rows_to_update:
                row.expected_amount = newly_expected_amount

            # perform bulk inserts
            db.bulk_save_objects(new_rotations)
            db.bulk_save_objects(new_rotating_contributions)
            db.bulk_save_objects(late_disbursements)

            # update the wallet balance
            user_record.wallet_balance -= adjustment_cost

            # update the activity account with the adjustment cost
            activity_account = db.query(models.Activity_Account).filter(models.Activity_Account.id == activity_id).with_for_update().first()
            activity_account.account_balance += adjustment_cost

            # update chama account
            chama_account = db.query(models.Chama_Account).filter(models.Chama_Account.id == activity.chama_id).with_for_update().first()
            chama_account.account_balance += adjustment_cost

            db.commit()

        return {"message": "Shares increased successfully"}
    except HTTPException as http_exc:
        transaction_error_logger.error(f"Failed to increase shares {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        transaction_error_logger.error(f"Failed to increase shares {exc}")
        raise HTTPException(
            status_code=400, detail="Failed to increase shares"
        )

# the following is of a member who is joining a merry-go-round late with one or more shares. this route will resemble the share increase route above
# just like in the share increase we will have to calculate the adjustment cost and validate the wallet balance, late disburse to the past rotations
# and contribute towards the upcoming contribution
# we will also add them to the activity_user association table, increase the expected amount for the rotation order and add rotating contributions
# update user wallet, activity and chama accounts - always check if user is already a member of the activity
@router.post("/join_merry_go_round_activity_late/{activity_id}", status_code=status.HTTP_201_CREATED)
async def join_merry_go_round_activity_late(
    activity_id: int,
    no_of_shares: schemas.merryGoRoundShareIncreaseReq = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).date()
        transaction_datetime = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        user_in_activity = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_id == current_user.id,
                )
            )
            # check if acquiring a lock is needed here
            .first()
        )

        if user_in_activity:
            raise HTTPException(
                status_code=404, detail="User is already a member of this activity"
            )

        # share increase activation data
        activation_record = (db.query(models.MerryGoRoundShareIncrease)
        .filter(
            and_(
                models.MerryGoRoundShareIncrease.activity_id == activity_id,
                models.MerryGoRoundShareIncrease.allow_new_members == True,
                func.date(models.MerryGoRoundShareIncrease.deadline) >= today,
            )
        )
        .first()
        )

        if not activation_record:
            raise HTTPException(
                status_code=404, detail="New members not allowed or deadline passed"
            )

        if no_of_shares.new_shares > activation_record.max_shares:
            raise HTTPException(
                status_code=404, detail="New shares exceed the maximum allowed shares"
            )

        # calculate adjustment cost and validate wallet balance
        cycle_number = (
            db.query(func.coalesce(func.max(models.RotationOrder.cycle_number), 0))
            .filter(models.RotationOrder.activity_id == activity_id)
            .scalar()
        )

        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )

        # retrieve all rotations in the current cycle upto the next contribution date
        rotations_to_clear = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                    models.RotationOrder.receiving_date <= next_contribution_date,
                )
            )
            .all()
        )

        if not rotations_to_clear:
            # this is okay since we are getting upto the next contribution date
            raise HTTPException(
                status_code=404, detail="No rotations to clear for this cycle"
            )

        # adjustment amount needed
        activity_amount = activity.activity_amount
        adjustment_fee = activation_record.adjustment_fee
        all_rotations_coverage = (len(rotations_to_clear) * activity_amount) * no_of_shares.new_shares
        adjustment_cost = all_rotations_coverage + adjustment_fee

        user_record = db.query(models.User).filter(models.User.id == current_user.id).with_for_update().first()
        if user_record.wallet_balance < adjustment_cost:
            raise HTTPException(
                status_code=400, detail="Insufficient wallet balance for adjustment, top up and try again"
            )

        with db.begin_nested():
            print("======begin nested===========")
            # add the user to the activity_user_association table
            new_user_in_activity = insert(models.activity_user_association).values(
                user_id=current_user.id,
                activity_id=activity_id,
                shares=no_of_shares.new_shares,
                share_value=activity.activity_amount,
                date_joined=transaction_datetime,
                is_active=True,
                is_deleted=False,
            )

            db.execute(new_user_in_activity)

            # add a rotation order record by first getting the last record in the current cycle
            last_rotation = (
                db.query(models.RotationOrder)
                .filter(
                    and_(
                        models.RotationOrder.activity_id == activity_id,
                        models.RotationOrder.cycle_number == cycle_number,
                    )
                )
                .order_by(desc(models.RotationOrder.order_in_rotation))
                .first()
            )

            if not last_rotation:
                raise HTTPException(
                    status_code=404, detail="No last rotation found"
                )

            # insert new records to the rotation order, users may have more than one new share, they will be added as consecutive records
            new_rotations = []
            newly_expected_amount = last_rotation.expected_amount + (activity_amount * no_of_shares.new_shares)
            next_receiving_date = None
            frequency = activity.frequency
            interval = activity.interval
            contribution_day = activity.contribution_day
            last_receiving_date = last_rotation.receiving_date

            for i in range(no_of_shares.new_shares):
                if frequency == "daily":
                    next_receiving_date = calculate_daily_interval(last_receiving_date)
                elif frequency == "weekly":
                    next_receiving_date = calculate_weekly_interval(last_receiving_date)
                elif frequency == "monthly" and interval in ["first", "second", "third", "fourth", "last"]:
                    next_receiving_date = calculate_monthly_interval(last_receiving_date, interval, contribution_day)
                elif frequency == "monthly" and interval == "monthly":
                    next_receiving_date = calculate_monthly_same_day_interval(last_receiving_date, int(contribution_day))
                elif frequency == "interval" and interval == "custom":
                    next_receiving_date = calculate_custom_interval(last_receiving_date, int(contribution_day))
                
                new_rotation = {
                    "user_name": f"{current_user.first_name} {current_user.last_name}",
                    "chama_id": activity.chama_id,
                    "activity_id": activity_id,
                    "recipient_id": current_user.id,
                    "share_value": activity_amount,
                    "receiving_date": next_receiving_date,
                    "expected_amount": newly_expected_amount,
                    "received_amount": 0,
                    "fulfilled": False,
                    "order_in_rotation": last_rotation.order_in_rotation + i + 1,
                    "share_name": share_names[i],
                    "cycle_number": cycle_number,
                }

                last_receiving_date = next_receiving_date

                new_rotations.append(models.RotationOrder(**new_rotation))

            # add  rotating contribution records for the new shares individually towards the next_contribution_date
            # we accounted for this in the adjustment_cost it will be like they have just contributed towards the upcoming contribution
            upcoming_recipient = (
                db.query(models.RotationOrder)
                .filter(
                    and_(
                        models.RotationOrder.activity_id == activity_id,
                        models.RotationOrder.cycle_number == cycle_number,
                        models.RotationOrder.receiving_date == next_contribution_date,
                    )
                )
                .first()
            )

            new_rotating_contributions = []
            for rotation in new_rotations:
                new_contribution = {
                    "chama_id": activity.chama_id,
                    "activity_id": activity_id,
                    "contributor_id": current_user.id,
                    "recipient_id": upcoming_recipient.recipient_id,
                    "expected_amount": activity_amount,
                    "contributed_amount": activity_amount,
                    "fine": 0,
                    "rotation_date": next_contribution_date,
                    "cycle_number": cycle_number,
                    "contributing_share": rotation.share_name,
                    "recipient_share": upcoming_recipient.share_name,
                    "contributed_on_time": True,
                }

                new_rotating_contributions.append(models.RotatingContributions(**new_contribution))

            # for this upcoming contribution to take effect we have to add a contribution record in the activities transactions table
            transaction_code = generate_transaction_code("contribution", user_record.wallet_id)
            contribution_record = models.ActivityTransaction(
                user_id=current_user.id,
                amount=activity_amount * no_of_shares.new_shares,
                origin=user_record.wallet_id,
                activity_id=activity_id,
                transaction_date=transaction_datetime,
                updated_at=transaction_datetime,
                transaction_completed=True,
                transaction_code=transaction_code,
                transaction_type="contribution",
            )

            db.add(contribution_record)

            # use the past rotations we got earlier excluding the upcoming rotation to now make new late disbursement records
            # since we have collected the missed amount this far and for the upcoming contribution day, we can now make sure the
            # recipients of the past rotations receive their share. the upcoming one has already been accounted for in the new rotating contributions
            late_disbursements = []

            for late_recipient in rotations_to_clear:
                if late_recipient.receiving_date == next_contribution_date:
                    continue

                late_disbursement = {
                    "chama_id": activity.chama_id,
                    "activity_id": activity_id,
                    "late_contribution": no_of_shares.new_shares * activity_amount,
                    "missed_rotation_date": late_recipient.receiving_date,
                    "disbursement_completed": False,
                    "late_contributor_id": current_user.id,
                    "late_recipient_id": late_recipient.recipient_id,
                }

                late_disbursements.append(models.LateRotationDisbursements(**late_disbursement))

            # now update all rotation order in the currect cycle their new expected amount since we just added new shares
            rows_to_update = db.query(models.RotationOrder).filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                )
            ).with_for_update().all()

            for row in rows_to_update:
                row.expected_amount = newly_expected_amount

            # perform bulk inserts
            db.bulk_save_objects(new_rotations)
            db.bulk_save_objects(new_rotating_contributions)
            db.bulk_save_objects(late_disbursements)

            # update the wallet balance
            user_record.wallet_balance -= adjustment_cost

            # update the activity account with the adjustment cost
            activity_account = db.query(models.Activity_Account).filter(models.Activity_Account.id == activity_id).with_for_update().first()
            activity_account.account_balance += adjustment_cost

            # update chama account
            chama_account = db.query(models.Chama_Account).filter(models.Chama_Account.id == activity.chama_id).with_for_update().first()
            chama_account.account_balance += adjustment_cost

            db.commit()

        return {"message": "New member added successfully"}
    except HTTPException as http_exc:
        transaction_error_logger.error(f"Failed to add new members {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        transaction_error_logger.error(f"Failed to add new member {exc}")
        raise HTTPException(
            status_code=400, detail="Failed to add new member"
        )