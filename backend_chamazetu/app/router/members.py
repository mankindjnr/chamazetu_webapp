from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/members", tags=["members"])


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
        print("============getting members contribution so far==========")
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
                    >= previous_contribution_date,
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
