from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List
import httpx
import logging
import os
from zoneinfo import ZoneInfo


from .. import schemas, database, utils, oauth2, models
from .stk_push import stk_push_status

router = APIRouter(prefix="/callback", tags=["callback"])

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")


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
        # Rollback the transaction in case of an error
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

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
        transaction_error_logger.error(f"Failed to update callback data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Callback data updated successfully."}


@router.put("/update_callback_transactions", status_code=status.HTTP_200_OK)
async def update_callback_transactions(
    db: Session = Depends(database.get_db),
):
    try:
        kenya_tz = ZoneInfo("Africa/Nairobi")
        five_minutes_ago = datetime.now(kenya_tz) - timedelta(minutes=5)

        # Retrieve all pending callback transactions
        pending_transactions = (
            db.query(models.CallbackData)
            .filter(models.CallbackData.Status == "Pending")
            .filter(models.CallbackData.TransactionDate <= five_minutes_ago)
            .all()
        )

        if pending_transactions:
            for transaction in pending_transactions:
                checkout_request_id = transaction.CheckoutRequestID

                # Call the stk_push_status function directly
                response = await stk_push_status(checkout_request_id)

                if response["message"] == "0 The transaction was successful":
                    # Update transaction status to success
                    transaction.Status = "Success"
                else:
                    # Update transaction status to failed with reason
                    transaction.Status = "Failed"
                    transaction.ResultCode = response["queryResponse"]["ResultCode"]

                db.add(transaction)

            db.commit()
        return {"message": "Callback transactions updated successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        # Handle any other exceptions
        db.rollback()
        transaction_error_logger.error(
            f"Failed to update callback transactions: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e))


# route will check the transactions table and retrieve transactions whose  transaction type is "unprocessed deposit", it will then compare those transactions against
# the callback data table using the cehckout request id, if in the callback data that transaction is marked as success, it will update the transaction table to success
# if not, it will update the transaction table to failed - later we can reverse all failed transactions
@router.put("/fix_callback_transactions_table_mismatch", status_code=status.HTTP_200_OK)
async def fix_mismatch_transactions(
    db: Session = Depends(database.get_db),
):

    try:
        # Retrieve all unprocessed deposit transactions
        unprocessed_deposits = (
            db.query(models.Transaction)
            .filter(models.Transaction.transaction_type == "unprocessed deposit")
            .filter(models.Transaction.transaction_origin == "mpesa")
            .filter(models.Transaction.transaction_completed == False)
            .all()
        )

        if unprocessed_deposits:
            for transaction in unprocessed_deposits:
                checkout_request_id = transaction.transaction_code

                # Retrieve the callback data for the given checkout id
                callback_data = (
                    db.query(models.CallbackData)
                    .filter(
                        models.CallbackData.CheckoutRequestID == checkout_request_id
                    )
                    .first()
                )

                if callback_data:
                    if callback_data.Status == "Success":
                        # the transaction needs to be reversed since it was not processed as it should have been
                        transaction.transaction_completed = True
                        transaction.needs_reversal = True
                    else:
                        # Update status to failed, the transaction was not successful - no further action needed
                        transaction.transaction_type = "failed"
                        transaction.needs_reversal = False

                    db.add(transaction)

            db.commit()
        return {"message": "Mismatch transactions updated successfully"}
    except Exception as e:
        # Handle any other exceptions
        db.rollback()
        transaction_error_logger.error(
            f"Failed to update mismatch transactions: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e))
