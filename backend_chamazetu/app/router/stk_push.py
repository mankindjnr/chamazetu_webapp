from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import and_, func, desc
from uuid import uuid4
import requests, os, base64, httpx, pytz
from dotenv import load_dotenv
from typing import List
from zoneinfo import ZoneInfo
import logging

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/request", tags=["request"])

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")


load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")
consumer_key = os.getenv("CONSUMER_KEY")
consumer_secret = os.getenv("CONSUMER_SECRET")
shortcode = os.getenv("SHORTCODE")
passkey = os.getenv("PASSKEY")


async def generate_access_token():
    url = os.getenv("OAUTH_URL")
    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {"Authorization": f"Basic {encoded_credentials}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()  # raise exception for non-2xx status codes
        return response.json()["access_token"]


def generate_password():
    timestamp = datetime.now(nairobi_tz).strftime("%Y%m%d%H%M%S")
    data_to_encode = shortcode + passkey + timestamp
    return base64.b64encode(data_to_encode.encode("utf-8")).decode("utf-8"), timestamp


# sending stk push request
@router.post("/push", status_code=status.HTTP_201_CREATED)
async def stk_push(
    push_data: schemas.StkPushBase = Body(...),
):
    token = await generate_access_token()
    if not token:
        raise HTTPException(status_code=500, detail="Failed to generate access token")

    password, timestamp = generate_password()
    callback_url = (
        "https://chamazetu.com/callback"
        if push_data.description != "Registration"
        else "https://chamazetu.com/callback/registration"
    )

    url = os.getenv("STK_PUSH_URL")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    phone_number = f"254{push_data.phone_number}"
    amount = push_data.amount
    recipient = push_data.recipient
    description = push_data.description

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": recipient,
        "TransactionDesc": description,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()  # raise exception for non-2xx status codes
        return response.json()


@router.get("/status/{checkout_request_id}")
async def stk_push_status(checkout_request_id: str):
    query_url = os.getenv("STK_PUSH_QUERY_URL")

    password, timestamp = generate_password()

    token = await generate_access_token()
    if not token:
        raise HTTPException(status_code=500, detail="Failed to get OAuth token")

    query_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    query_payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                query_url, headers=query_headers, json=query_payload
            )
            response.raise_for_status()  # Raise exception for non-2xx status codes
            response_data = response.json()

            if "ResultCode" in response_data:
                result_code = response_data["ResultCode"]
                if result_code == "1037":
                    message = "1037 Timeout in completing transaction"
                elif result_code == "1032":
                    message = "1032 Transaction has been canceled by the user"
                elif result_code == "1":
                    message = "1 The balance is insufficient for the transaction"
                elif result_code == "0":
                    message = "0 The transaction was successful"
                else:
                    message = "Unknown result code: " + result_code
            else:
                message = "Error in response"

            return {"message": message, "queryResponse": response_data}
    except httpx.RequestError as e:
        transaction_error_logger.error(f"HTTP request error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to query STK push status")
    except httpx.HTTPStatusError as e:
        transaction_error_logger.error(f"HTTP status error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to query STK push status")
    except ValueError as e:
        transaction_error_logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to query STK push status")
