from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import logging
from typing import List
from uuid import uuid4
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/members", tags=["members"])

nairobi_tz = ZoneInfo("Africa/Nairobi")

logger = logging.getLogger(__name__)


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
                )
            )
            .order_by(desc(models.Transaction.date_of_transaction))
            .limit(7)
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
    "/update_wallet_balance",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberWalletBalanceResp,
)
async def update_member_wallet_balance(
    wallet_data: schemas.UpdateWalletBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):

    try:
        print("===========wallet update===========")
        wallet_dict = wallet_data.dict()
        amount = wallet_dict["amount"]
        transaction_type = wallet_dict["transaction_type"]
        wallet_dict["member_id"] = current_user.id
        wallet_dict["transaction_completed"] = True
        wallet_dict["transaction_date"] = datetime.now(nairobi_tz)
        wallet_dict["transaction_code"] = wallet_dict["transaction_code"]

        member = (
            db.query(models.Member).filter(models.Member.id == current_user.id).first()
        )

        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        if (
            transaction_type == "deposited_to_wallet"
            or transaction_type == "moved_to_wallet"
        ):
            new_wallet_balance = member.wallet_balance + amount
        elif (
            transaction_type == "withdrawn_from_wallet"
            or transaction_type == "moved_to_chama"
        ):
            new_wallet_balance = member.wallet_balance - amount
        else:
            raise HTTPException(status_code=400, detail="Invalid transaction type")

        member.wallet_balance = new_wallet_balance
        db.commit()
        db.refresh(member)

        new_transaction = models.Wallet_Transaction(**wallet_dict)
        db.add(new_transaction)
        db.commit()
        return {"wallet_balance": member.wallet_balance}
    except Exception as e:
        print("========error updating wallet balance========")
        print(e)
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


# retrieve wallet activity for a member, latest 7 transactions
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
            .order_by(desc(models.Wallet_Transaction.transaction_date))
            .limit(5)
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
        print("========error getting recent wallet activity========")
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get members recent wallet activity"
        )


# repaying fines for a member in a certain chama - we will pull all the unpaid fines for a member in a chama and loop through the earliest using fine_date, we we use the amout we receive from the member
# and the total_expected_amount in the fine table for deduction, after every deduction, we update the fine table, with a ew total_expected_amount and proceed to the next fine,


# might check on adding headers to the request to make sure the member is the one making the request
@router.put(
    "/repay_fines",
    status_code=status.HTTP_200_OK,
    response_model=schemas.MemberFineResp,
)
async def repay_fines(
    fine_data: schemas.MemberFineBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        print("===========repaying fines===========")
        fine_dict = fine_data.dict()
        chama_id = fine_dict["chama_id"]
        member_id = fine_dict["member_id"]
        amount = fine_dict["amount"]

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
            .all()
        )

        if not fines:
            #  this means the member has no fines to pay so we return the amount to the member fror the transaction to be completed
            return {"balance_after_fines": amount}

        for fine in fines:
            print("===========repaying fine===========")
            print(fine)
            print()
            print(fine.total_expected_amount)
            print("==start:", amount)
            if amount >= fine.total_expected_amount:
                amount -= (
                    fine.total_expected_amount
                )  # deducting the amount from the fine and updating amount to be used in the next fine
                fine.is_paid = True
                # date in nairobi timezone
                fine.paid_date = datetime.now(nairobi_tz)
                fine.total_expected_amount = 0
                print("==end==:", amount)
            else:
                print("===========less fine===========")
                fine.total_expected_amount -= amount
                amount = 0
                print(amount)
                break

        db.commit()  # committing all the changes to the database

        # # reffreshing
        # for fine in fines:
        #     db.refresh(fine)
        print("===========fines repaid===========")
        print(amount)
        return {"balance_after_fines": amount}

    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to repay fines")


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
        print("===========error checking fines===========")
        print(e)
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
            return {"total_fines": 0}

        total_fine_amount = 0
        for fine in fines:
            total_fine_amount += fine.total_expected_amount

        # return true if the member has fines to pay

        return {"total_fines": total_fine_amount}

    except Exception as e:
        print("===========error getting total fines===========")
        print(e)
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
        print("===========error checking chama membership===========")
        print(e)
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

        logger.warning(
            "Chamas share price and previous two contribution dates retrieved"
        )
        logger.warning(chamas_details)

        return chamas_details
    except Exception as e:
        print(e)
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
@router.get(
    "/members_and_contribution_fines",
    status_code=status.HTTP_200_OK,
)
async def get_members_and_contribution_fines(
    chama_details: dict,
    db: Session = Depends(database.get_db),
):
    try:
        chamas_details = chama_details
        fines = {}
        for chama_id, chama_details in chamas_details.items():
            chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
            chama_members = (
                db.query(models.Member)
                .join(models.members_chamas_association)
                .filter(models.members_chamas_association.c.chama_id == chama_id)
                .filter(
                    models.members_chamas_association.c.registration_fee_paid == True
                )
                .all()
            )

            if chama_members:
                for member in chama_members:
                    logger.warning("Member: " + member.first_name)
                    member_chama = (
                        db.query(models.members_chamas_association)
                        .filter(
                            and_(
                                models.members_chamas_association.c.member_id
                                == member.id,
                                models.members_chamas_association.c.chama_id
                                == chama_id,
                            )
                        )
                        .first()
                    )

                    prev_contribution_datetime = datetime.fromisoformat(
                        chama_details["prev_contribution_date"]
                    )

                    prev_two_contribution_datetime = datetime.fromisoformat(
                        chama_details["prev_two_contribution_date"]
                    )

                    member_contribution = (
                        db.query(models.Transaction)
                        .filter(
                            and_(
                                models.Transaction.member_id == member.id,
                                models.Transaction.chama_id == chama_id,
                                models.Transaction.transaction_type == "deposit",
                                models.Transaction.transaction_completed == True,
                                func.date(models.Transaction.date_of_transaction)
                                > prev_two_contribution_datetime.date(),
                                func.date(models.Transaction.date_of_transaction)
                                <= prev_contribution_datetime.date(),
                            )
                        )
                        .all()
                    )
                    total_contribution = sum(
                        [transaction.amount for transaction in member_contribution]
                    )
                    logger.warning("Total contribution: " + str(total_contribution))

                    expected_contribution = (
                        chama.contribution_amount * member_chama.num_of_shares
                    )
                    logger.warning(
                        "Expected contribution: " + str(expected_contribution)
                    )
                    difference = expected_contribution - total_contribution
                    logger.warning("Difference: " + str(difference))
                    fine = 0
                    if difference > 0:
                        logger.warning("Fine to be added")
                        fine = member_chama.num_of_shares * chama.fine_per_share

                        fines[member.id] = {
                            "chama_id": chama_id,
                            "member_id": member.id,
                            "fine": fine,
                            "fine_reason": "Missed contribution",
                            "fine_date": chama_details["prev_contribution_date"],
                            "is_paid": False,
                            "paid_date": None,
                            "total_expected_amount": fine + difference,
                        }
                        # write the record to the fines table but i want if such a record exists, if a record with member_id, chama_id, fine_date exists, dont write another record
                        # if it doesnt exist, write the record
                        # prev_contribution_datetime = datetime.fromisoformat(
                        #     chama_details["prev_contribution_date"]
                        # )
                        # if prev contribution date is today, dont write a fine or if prev contribution date is in the future, dont write a fine
                        # this is because the contribution period has not passed yet
                        # if (
                        #     prev_contribution_datetime.date() == datetime.now().date()
                        #     or prev_contribution_datetime.date() > datetime.now().date()
                        # ):
                        #     continue

                        existing_fine = (
                            db.query(models.Fine)
                            .filter(
                                and_(
                                    models.Fine.member_id == member.id,
                                    models.Fine.chama_id == chama_id,
                                    func.date(models.Fine.fine_date)
                                    == prev_contribution_datetime.date(),
                                )
                            )
                            .first()
                        )

                        if not existing_fine:
                            logger.warning("Fine record does not exist")
                            new_fine = models.Fine(
                                chama_id=chama_id,
                                member_id=member.id,
                                fine=fine,
                                fine_reason="Missed contribution",
                                fine_date=chama_details["prev_contribution_date"],
                                is_paid=False,
                                paid_date=None,
                                total_expected_amount=fine + difference,
                            )
                            db.add(new_fine)
                            db.commit()
                            db.refresh(new_fine)
        logger.warning("Fines added")
        logger.warning(fines)
        logger.warning("=====================")
        return {"fines": fines}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=400,
            detail="Failed to retrieve and set members and contribution fines",
        )
