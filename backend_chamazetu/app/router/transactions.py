from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List


from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/transactions", tags=["transactions"])


# create deposit transaction for a logged in member to chama
@router.post(
    "/deposit",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.TransactionResp,
)
async def create_deposit_transaction(
    transaction: schemas.TransactionBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    try:
        transaction_dict = transaction.dict()
        transaction_dict["transaction_type"] = "deposit"
        transaction_dict["member_id"] = current_user.id
        transaction_dict["transaction_completed"] = True
        transaction_dict["date_of_transaction"] = datetime.now()
        transaction_dict["updated_at"] = datetime.now()
        transaction_dict["transaction_code"] = uuid4().hex

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        return new_transaction

    except Exception as e:
        print("------error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# fetch transactions for a certain chama
@router.get(
    "/{chamaname}",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.RecentTransactionResp],
)
async def get_transactions(
    chama_id: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        chama_id = chama_id["chama_id"]

        transactions = (
            db.query(models.Transaction)
            .filter(
                and_(
                    models.Transaction.chama_id == chama_id,
                    models.Transaction.transaction_completed == True,
                )
            )
            .order_by(desc(models.Transaction.date_of_transaction))
            .limit(5)
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
