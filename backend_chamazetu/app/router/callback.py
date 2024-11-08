from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List
import httpx
import logging
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()


from .. import schemas, database, utils, oauth2, models
from app.celery import process_callback, chama_registration_callback, process_b2c_result, complete_unprocessed_deposit
from .stk_push import stk_push_status, generate_access_token, generate_password

router = APIRouter(prefix="/callback", tags=["callback"])

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")

nairobi_tz = ZoneInfo("Africa/Nairobi")


# transaction status function
@router.put(
    "/fix_unprocessed_deposit/{unprocessed_code}/{receipt_number}",
    status_code=status.HTTP_200_OK,
)
async def check_transaction_status(
    unprocessed_code: str,
    receipt_number: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
) -> dict:
    try:
        user = db.query(models.User).filter(models.User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # Retrieve the transaction
        transaction = (
            db.query(models.WalletTransaction)
            .filter(models.WalletTransaction.transaction_code == unprocessed_code)
            .first()
        )

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )

        url = os.getenv("TRANSACTION_STATUS_URL")
        access_token = await generate_access_token()
        password, timestamp = generate_password()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        payload = {
            "Initiator": os.getenv("STATUS_CHECK_INITIATOR_NAME"),
            "SecurityCredential": os.getenv("STATUS_CHECK_SECURITY_CREDENTIAL"),
            "CommandID": "TransactionStatusQuery",
            "TransactionID": receipt_number,
            "OriginatorConversationID": unprocessed_code,
            "PartyA": 4138859,
            "IdentifierType": "4",
            "ResultURL": "https://20jb26ww-9400.uks1.devtunnels.ms/callback/status/result",
            "QueueTimeOutURL": "https://chamazetu.com/api/TransactionStatus/queue",
            "Remarks": "Transaction status query",
            "Occasion": f"{current_user.id}/{unprocessed_code}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()

        return response_data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="An error occurred while processing the transaction."
        )
"""
====response_data====
{'OriginatorConversationID': 'bcd8-4d43-b6a9-f918f352a9e329921621', 'ConversationID': 'AG_20241108_2020651bad15260c074b', 'ResponseCode': '0', 'ResponseDescription': 'Accept the service request successfully.'}
"""
# status result function
@router.post("/status/result", status_code=status.HTTP_201_CREATED)
async def status_result(result: dict):
    print("=====status result=====")
    # print(result)
    complete_unprocessed_deposit.delay(result)
    transaction_info_logger.info(f"Received status result: {result}")
    return {"message": "Status result processed successfully."}


@router.post("/data", status_code=status.HTTP_201_CREATED)
async def callback_data(
    transaction_data: schemas.MpesaResponse = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
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
            Purpose="wallet",
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


def get_phone_number(result):
    phone_number = result["Result"]["ResultParameters"]["ResultParameter"][2][
        "Value"
    ].split(" - ")[0]

    if len(phone_number) == 10:
        return f"254{phone_number[1:]}"

    return phone_number


def extract_originator_conversation_id(result: dict) -> str:
    return result.get("Result", {}).get("OriginatorConversationID", "")


def convert_date_format(date_str: str) -> str:
    # Define the current format of the date string
    current_format = "%d.%m.%Y %H:%M:%S"

    # Define the desired output format
    desired_format = "%Y-%m-%d %H:%M:%S"

    # Parse the input date string into a datetime object
    date_obj = datetime.strptime(date_str, current_format)

    # Convert the datetime object to the desired string format
    formatted_date = date_obj.strftime(desired_format)

    return formatted_date


def extract_result_parameters(result: dict) -> dict:
    result_parameters = result["Result"]["ResultParameters"]["ResultParameter"]
    extracted_result = {param["Key"]: param["Value"] for param in result_parameters}
    return extracted_result


@router.post("/b2c/result", status_code=status.HTTP_201_CREATED)
async def b2c_result(result: dict):
    print("=====b2c result=====")
    # print(result)
    process_b2c_result.delay(result)
    transaction_info_logger.info(f"Received B2C result: {result}")
    return {"message": "B2C result processed successfully."}


@router.post("/b2c/queue", status_code=status.HTTP_201_CREATED)
async def b2c_queue(timeout: dict):
    print("=====b2c timeout=====")
    print(timeout)
    transaction_error_logger.error(f"Failed to update transaction\n: {timeout}")
    return {"message": "B2C timeout processed successfully."}


@router.post("/c2b/{unprocessed_code}", status_code=status.HTTP_201_CREATED)
async def c2b_callback(unprocessed_code: str, transaction_data: dict):
    print("=====enquieng c2b callback=====")
    process_callback.delay(unprocessed_code, transaction_data)
    return {"message": "callback received, processing task enqueued"}


# a better registration callback
@router.post("/registration/{unprocessed_code}", status_code=status.HTTP_201_CREATED)
async def chama_registration(unprocessed_code: str, registration_data: dict):
    print("=====enquieng registration callback=====")
    chama_registration_callback.delay(unprocessed_code, registration_data)
    return {"message": "callback received, processing task enqueued"}