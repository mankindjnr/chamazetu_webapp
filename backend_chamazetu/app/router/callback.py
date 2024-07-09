from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Request
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List


from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/callback", tags=["callback"])


@router.post("/data", status_code=status.HTTP_201_CREATED)
async def callback_data(
    transaction_data: schemas.MpesaResponse = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        # Start a new transaction
        # db.begin()
        transaction_date = datetime.strptime(
            str(transaction_data.TransactionDate), "%Y%m%d%H%M%S"
        )

        # Store the data in the callback table
        new_callback = models.CallbackData(
            MerchantRequestID=transaction_data.MerchantRequestID,
            CheckoutRequestID=transaction_data.CheckoutRequestID,
            ResultCode=transaction_data.ResultCode,
            ResultDesc=transaction_data.ResultDesc,
            Amount=transaction_data.Amount,
            MpesaReceiptNumber=transaction_data.MpesaReceiptNumber,
            TransactionDate=transaction_date,
            PhoneNumber=transaction_data.PhoneNumber,
            Purpose="chama",
            Status="Pending",
        )
        db.add(new_callback)

        # Commit the transaction
        db.commit()
        db.refresh(new_callback)

    except Exception as e:
        print(e)
        # Rollback the transaction in case of an error
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the transaction.",
        )

    finally:
        # Close the session
        db.close()

    return {"message": "Transaction processed successfully."}


@router.post("/registration", status_code=status.HTTP_201_CREATED)
async def registration_callback(
    transaction_data: schemas.MpesaResponse = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        # Start a new transaction
        # db.begin()
        transaction_date = datetime.strptime(
            str(transaction_data.TransactionDate), "%Y%m%d%H%M%S"
        )

        # Store the data in the callback table
        new_callback = models.CallbackData(
            MerchantRequestID=transaction_data.MerchantRequestID,
            CheckoutRequestID=transaction_data.CheckoutRequestID,
            ResultCode=transaction_data.ResultCode,
            ResultDesc=transaction_data.ResultDesc,
            Amount=transaction_data.Amount,
            MpesaReceiptNumber=transaction_data.MpesaReceiptNumber,
            TransactionDate=transaction_date,
            PhoneNumber=transaction_data.PhoneNumber,
            Purpose="Registration",
            Status="Pending",
        )
        db.add(new_callback)

        # Commit the transaction
        db.commit()
        db.refresh(new_callback)

    except Exception as e:
        print(e)
        # Rollback the transaction in case of an error
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the transaction.",
        )

    finally:
        # Close the session
        db.close()

    return {"message": "Transaction processed successfully."}


# update call backdta status to success
@router.put("/update_pending_callback_data", status_code=status.HTTP_200_OK)
async def update_pending_callback_data(
    checkout_data: schemas.UpdateCallbackData = Body(...),
    db: Session = Depends(database.get_db),
):

    checkoutid = checkout_data.checkoutid

    try:
        db.query(models.CallbackData).filter(
            models.CallbackData.CheckoutRequestID == checkoutid
        ).update({"Status": "Success"})
        db.commit()
    except Exception as e:
        print(e)
        # Rollback the transaction in case of an error
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the transaction.",
        )
    finally:
        # Close the session
        db.close()
