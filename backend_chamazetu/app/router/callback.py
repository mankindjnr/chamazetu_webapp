from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
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


@router.put(
    "/update_pending_callback_data/{checkoutid}", status_code=status.HTTP_200_OK
)
async def update_pending_callback_data(
    checkoutid: str,
    db: Session = Depends(database.get_db),
):
    print("===================call back===========================")
    try:
        # Retrieve the callback data for the given checkout id with a lock for update
        callback_data = (
            db.query(models.CallbackData)
            .filter(models.CallbackData.CheckoutRequestID == checkoutid)
            .with_for_update()
            .first()
        )

        if not callback_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Callback data not found.",
            )

        # Update the status of the callback data to success
        callback_data.Status = "Success"
        db.commit()  # Commit the transaction
    except SQLAlchemyError as e:
        db.rollback()  # Rollback the transaction in case of an error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the transaction.",
        ) from e

    return {"message": "Callback data updated successfully."}
