from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import and_
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
        transaction_dict["transaction_code"] = uuid4().hex

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        print("------new transaction--------")
        print(new_transaction)
        return new_transaction

    except Exception as e:
        print("------error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# fetch transactions for a certain chama
@router.get(
    "/{chamaname}",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.TransactionResp],
)
async def get_transactions(
    chama_id: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        chama_id = chama_id["chama_id"]
        print("chama_id", chama_id)
        transactions = (
            db.query(models.Transaction)
            .filter(models.Transaction.chama_id == chama_id)
            .all()
        )

        return [
            schemas.TransactionResp(**transaction.__dict__)
            for transaction in transactions
        ]
    except Exception as e:
        print("------chamaname chama error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to fetch transactions")


# fetch transaction for a certain member using id and chama_id
@router.get(
    "/chama_transactions/{member_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.TransactionResp],
)
async def get_transactions(
    data: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        member_id = data.get("member_id")
        print("member_id", member_id)
        transactions = (
            db.query(models.Transaction)
            .filter(models.Transaction.member_id == member_id)
            .filter(models.Transaction.chama_id == 1)
            .all()
        )

        return [
            schemas.TransactionResp(**transaction.__dict__)
            for transaction in transactions
        ]
    except Exception as e:
        print("------transactions chama error--------")
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to individual member fetch transactions"
        )
