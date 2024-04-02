from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session

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

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)

        print("------new transaction--------")
        print(new_transaction)
        return new_transaction

        # return {"Transaction": [new_transaction]}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")
