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
    "/direct_deposit",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.TransactionResp,
)
async def create_deposit_transaction(
    transaction: schemas.DirectTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        with db.begin():
            transaction_dict = transaction.dict()
            transaction_dict["transaction_type"] = "deposit"
            transaction_dict["member_id"] = transaction.member_id
            transaction_dict["transaction_completed"] = True
            transaction_dict["date_of_transaction"] = datetime.now()
            transaction_dict["updated_at"] = datetime.now()
            transaction_dict["transaction_code"] = transaction.transaction_code

            new_transaction = models.Transaction(**transaction_dict)
            db.add(new_transaction)
            db.flush()  # flush to get the id of the transaction and trigger constraints
            db.refresh(new_transaction)

        return new_transaction

    except Exception as e:
        print("------direct deposit error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# create a deposit transaction from wallet to chama
@router.post(
    "/deposit_from_wallet",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.WalletTransactionResp,
)
async def create_deposit_transaction_from_wallet(
    wallet_transaction: schemas.WalletTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):

    try:
        print("===========hit wallet transaction===========")
        wallet_transaction_dict = wallet_transaction.dict()
        wallet_transaction_dict["transaction_type"] = "moved_to_chama"
        wallet_transaction_dict["member_id"] = current_user.id
        wallet_transaction_dict["transaction_completed"] = True
        wallet_transaction_dict["transaction_date"] = datetime.now()
        wallet_transaction_dict["transaction_code"] = uuid4().hex

        print("===========wallet transaction dict===========")
        print(wallet_transaction_dict)

        new_wallet_transaction = models.Wallet_Transaction(**wallet_transaction_dict)
        db.add(new_wallet_transaction)
        db.commit()
        db.refresh(new_wallet_transaction)

        # add record to transactions table
        transaction_dict = {
            "amount": new_wallet_transaction.amount,
            "phone_number": generateWalletNumber(current_user.id),
            "chama_id": wallet_transaction.transaction_destination,
            "transaction_type": "deposit",
            "transaction_origin": "wallet_deposit",
            "member_id": current_user.id,
            "transaction_completed": True,
            "date_of_transaction": new_wallet_transaction.transaction_date,
            "updated_at": new_wallet_transaction.transaction_date,
            "transaction_code": new_wallet_transaction.transaction_code,
        }

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()

        return new_wallet_transaction

    except Exception as e:
        print("------deposit from wallet error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# TODO: above to support fines
# ============duplicate of the above to repay fines================
@router.post(
    "/record_fine_payment",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.WalletTransactionResp,
)
async def create_fine_repayment_transaction_from_wallet(
    wallet_transaction: schemas.WalletTransactionBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):

    try:
        print("===========record fine wallet transaction===========")
        wallet_transaction_dict = wallet_transaction.dict()
        wallet_transaction_dict["transaction_type"] = "moved_to_chama"
        wallet_transaction_dict["member_id"] = current_user.id
        wallet_transaction_dict["transaction_completed"] = True
        wallet_transaction_dict["transaction_date"] = datetime.now()
        wallet_transaction_dict["transaction_code"] = uuid4().hex

        print("===========wallet transaction dict===========")
        print(wallet_transaction_dict)

        new_wallet_transaction = models.Wallet_Transaction(**wallet_transaction_dict)
        db.add(new_wallet_transaction)
        db.commit()
        db.refresh(new_wallet_transaction)

        # add record to transactions table
        transaction_dict = {
            "amount": new_wallet_transaction.amount,
            "phone_number": generateWalletNumber(current_user.id),
            "chama_id": wallet_transaction.transaction_destination,
            "transaction_type": "fine deduction",
            "transaction_origin": "wallet_deposit",
            "member_id": current_user.id,
            "transaction_completed": True,
            "date_of_transaction": new_wallet_transaction.transaction_date,
            "updated_at": new_wallet_transaction.transaction_date,
            "transaction_code": new_wallet_transaction.transaction_code,
        }

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()

        return new_wallet_transaction

    except Exception as e:
        print("------deposit from wallet error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# =========================mpesa fine repayment recording=========
@router.post(
    "/record_fine_payment_from_mpesa",
    status_code=status.HTTP_201_CREATED,
)
async def create_fine_repayment_transaction_from_mpesa(
    mpesa_transaction: schemas.MpesaPayFinesBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        print("===========record fine mpesa transaction===========")

        # add record to transactions table
        transaction_dict = {
            "amount": mpesa_transaction.amount,
            "phone_number": mpesa_transaction.phone_number,
            "chama_id": mpesa_transaction.transaction_destination,
            "transaction_type": "fine deduction",
            "transaction_origin": "direct_deposit",
            "member_id": mpesa_transaction.member_id,
            "transaction_completed": True,
            "date_of_transaction": datetime.now(),
            "updated_at": datetime.now(),
            "transaction_code": mpesa_transaction.transaction_code,
        }

        new_transaction = models.Transaction(**transaction_dict)
        db.add(new_transaction)
        db.commit()

        return

    except Exception as e:
        print("------deposit from mpesa error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create transaction")


# ================================================================


def generateWalletNumber(member_id):
    prefix = "94" + str(member_id)
    wallet_number = prefix.zfill(12)
    return wallet_number


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
