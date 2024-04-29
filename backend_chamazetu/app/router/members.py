from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from uuid import uuid4
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/members", tags=["members"])


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
        ).strftime("%Y-%m-%d")
        upcoming_contribution_date = datetime.strptime(
            member_dict["upcoming_contribution_date"], "%d-%m-%Y"
        ).strftime("%Y-%m-%d")
        member_transactions = (
            db.query(models.Transaction)
            .filter(
                and_(
                    models.Transaction.chama_id == chama_id,
                    models.Transaction.member_id == member_id,
                    models.Transaction.transaction_completed == True,
                    models.Transaction.is_reversed == False,
                    func.date(models.Transaction.date_of_transaction)
                    > previous_contribution_date,
                    func.date(models.Transaction.date_of_transaction)
                    <= upcoming_contribution_date,
                )
            )
            .order_by(desc(models.Transaction.date_of_transaction))
            .all()
        )

        member_contribution = 0
        for transaction in member_transactions:
            member_contribution += transaction.amount

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
        wallet_dict["transaction_date"] = datetime.now()
        wallet_dict["transaction_code"] = uuid4().hex

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
