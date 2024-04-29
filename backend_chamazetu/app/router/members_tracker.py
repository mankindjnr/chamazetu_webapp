from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Union
from collections import defaultdict
from uuid import uuid4
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/members_tracker", tags=["members_tracker"])


@router.get(
    "/members_daily_monthly_contribution/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_members_daily_monthly_contribution(
    chama_id: int,
    back_date_data: dict = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        back_date = datetime.strptime(
            back_date_data["contribution_back_date"], "%d-%m-%Y"
        ).strftime("%Y-%m-%d")
        # get all members in a chama
        chama_members = (
            db.query(models.Member)
            .join(models.members_chamas_association)
            .filter(models.members_chamas_association.c.chama_id == chama_id)
            .all()
        )
        members_daily_contribution = defaultdict(lambda: defaultdict(int))

        for member in chama_members:
            member_dict = member.__dict__
            member_id = member_dict["id"]

            # get all transactions for a member
            member_transactions = (
                db.query(models.Transaction)
                .filter(
                    and_(
                        models.Transaction.chama_id == chama_id,
                        models.Transaction.member_id == member_id,
                        models.Transaction.transaction_completed == True,
                        func.date(models.Transaction.date_of_transaction) > back_date,
                    )
                )
                .all()
            )
            for transaction in member_transactions:
                transaction_dict = transaction.__dict__
                transaction_dict.pop("_sa_instance_state")
                transaction_date = transaction_dict["date_of_transaction"].strftime(
                    "%d-%m-%Y"
                )
                transaction_amount = transaction_dict["amount"]

                members_daily_contribution[member_id][
                    transaction_date
                ] += transaction_amount

        return {"members_contribution": members_daily_contribution}

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get members daily monthly contribution"
        )


# get what members have contributed in a chama in a given period
@router.get(
    "/chama_days_contribution_tracker/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_days_contribution_tracker(
    chama_id: int,
    dates_data: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        upto_date = datetime.strptime(dates_data["upto_date"], "%d-%m-%Y").strftime(
            "%Y-%m-%d"
        )
        from_date = datetime.strptime(dates_data["from_date"], "%d-%m-%Y").strftime(
            "%Y-%m-%d"
        )

        # get all members in a chama
        chama_members = (
            db.query(models.Member)
            .join(models.members_chamas_association)
            .filter(models.members_chamas_association.c.chama_id == chama_id)
            .all()
        )
        chama_daily_contribution = defaultdict(lambda: defaultdict(int))

        for member in chama_members:
            member_dict = member.__dict__
            member_id = member_dict["id"]

            # get all transactions for a member
            member_transactions = (
                db.query(models.Transaction)
                .filter(
                    and_(
                        models.Transaction.chama_id == chama_id,
                        models.Transaction.member_id == member_id,
                        models.Transaction.transaction_completed == True,
                        func.date(models.Transaction.date_of_transaction) > from_date,
                        func.date(models.Transaction.date_of_transaction) <= upto_date,
                    )
                )
                .all()
            )
            for transaction in member_transactions:
                transaction_dict = transaction.__dict__
                transaction_dict.pop("_sa_instance_state")
                transaction_date = transaction_dict["date_of_transaction"].strftime(
                    "%d-%m-%Y"
                )
                transaction_amount = transaction_dict["amount"]

                chama_daily_contribution[member_id][
                    transaction_date
                ] += transaction_amount

        print("=========chama_daily_contribution=========")
        print(chama_daily_contribution)

        return {"chama_contribution": chama_daily_contribution}

    except Exception as e:
        print("=========error with chama days contribution tracker=========")
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get chama days contribution tracker"
        )


# get all the members in a chama, email and first name, last name
@router.get(
    "/chama_members/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.ChamaMembersList],
)
async def get_chama_members(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        chama_members = (
            db.query(models.Member)
            .join(models.members_chamas_association)
            .filter(models.members_chamas_association.c.chama_id == chama_id)
            .all()
        )

        return [schemas.ChamaMembersList.from_orm(member) for member in chama_members]

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to get chama members")
