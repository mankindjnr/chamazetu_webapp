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
import asyncio
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/request", tags=["request"])

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")

load_dotenv()

TIMEOUT = 10

nairobi_tz = ZoneInfo("Africa/Nairobi")
consumer_key = os.getenv("CONSUMER_KEY")
consumer_secret = os.getenv("CONSUMER_SECRET")
shortcode = os.getenv("SHORTCODE")
passkey = os.getenv("PASSKEY")
initiator_name = os.getenv("INITIATOR_NAME")
initiator_password = os.getenv("INITIATOR_PASSWORD")
security_credential = os.getenv("SECURITY_CREDENTIAL")


def load_public_key():
    try:
        with open(
            "public_key.pem", "rb"
        ) as cert_file:  # Or "ProductionCertificate.cer"
            public_key = serialization.load_pem_public_key(
                cert_file.read(), backend=default_backend()
            )
        print("Public key loaded successfully")
        return public_key
    except Exception as e:
        print(f"Failed to load public key: {str(e)}")
        return None


def encrypt_security_credential(plaintext_password: str) -> str:
    public_key = load_public_key()
    if public_key is None:
        raise Exception("Failed to load public key.")

    # Encrypt the password
    encrypted_password = public_key.encrypt(
        plaintext_password.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    # Return the base64 encoded encrypted string
    return base64.b64encode(encrypted_password).decode("utf-8")


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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type(httpx.RequestError),
)
async def perform_stk_push(
    client: httpx.AsyncClient, url: str, headers: dict, payload: dict
):
    """performs the stk push request with retries"""
    try:
        response = await client.post(
            url, headers=headers, json=payload, timeout=TIMEOUT
        )
        response.raise_for_status()  # raise exception for non-2xx status codes
        return response.json()
    except httpx.TimeoutException:
        transaction_error_logger.error("Request timed out")
        raise
    except httpx.RequestError as exc:
        transaction_error_logger.error(f"HTTP request error: {str(exc)}")
        raise
    except httpx.Exception as e:
        transaction_error_logger.error(f"HTTP status error: {str(e)}")
        raise


# stk push route
@router.post("/push", status_code=status.HTTP_201_CREATED)
async def stk_push(
    push_data: schemas.StkPushBase = Body(...),
):
    token = await generate_access_token()
    if not token:
        raise HTTPException(status_code=500, detail="Failed to generate access token")

    password, timestamp = generate_password()
    callback_url = (
        "https://chamazetu.com/api/callback/c2b"
        if push_data.description != "Registration"
        else "https://chamazetu.com/api/callback/registration"
    )

    url = os.getenv("STK_PUSH_URL")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    phone_number = push_data.phone_number
    amount = push_data.amount
    recipient = push_data.transaction_destination
    description = push_data.description
    unprocessed_code = push_data.transaction_code

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": f"{callback_url}/{unprocessed_code}",
        "AccountReference": recipient,
        "TransactionDesc": description,
    }

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
    ) as client:
        try:
            response = await perform_stk_push(client, url, headers, payload)
            return response
        except httpx.RequestError as e:
            transaction_error_logger.error(f"HTTP request error: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to initiate STK push")
        except httpx.HTTPStatusError as e:
            transaction_error_logger.error(f"HTTP status error: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to initiate STK push")
        except ValueError as e:
            transaction_error_logger.error(f"Value error: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to initiate STK push")
        except Exception as e:
            transaction_error_logger.error(f"Error: {str(e)}")
            raise HTTPException(status_code=400, detail="Failed to initiate STK push")


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

            return response_data
    except httpx.RequestError as e:
        transaction_error_logger.error(f"HTTP request error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to query STK push status")
    except httpx.HTTPStatusError as e:
        transaction_error_logger.error(f"HTTP status error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to query STK push status")
    except ValueError as e:
        transaction_error_logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to query STK push status")


@router.post("/send", status_code=status.HTTP_201_CREATED)
async def send_money(
    send_data: schemas.SendMoneyBase = Body(...),
):
    token = await generate_access_token()
    if not token:
        raise HTTPException(status_code=500, detail="Failed to generate access token")

    password, timestamp = generate_password()
    url = os.getenv("B2C_URL")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    phone_number = send_data.phone_number
    amount = send_data.amount
    description = send_data.description
    originator_id = send_data.originator_conversation_id

    payload = {
        "OriginatorConversationID": originator_id,
        "InitiatorName": initiator_name,
        "SecurityCredential": security_credential,
        "CommandID": "BusinessPayment",
        "Amount": amount,
        "PartyA": shortcode,
        "PartyB": phone_number,
        "Remarks": description,
        "QueueTimeOutURL": "https://chamazetu.com/api/callback/b2c/queue",
        "ResultURL": "https://chamazetu.com/api/callback/b2c/result",
        "Occasion": "WITHDRAWAL",
    }

    # print("==payload==\n", payload)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print("=====sending======")
            print(response.json())
            return response.json()
    except httpx.RequestError as e:
        transaction_error_logger.error(f"HTTP request error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to send money")
    except httpx.HTTPStatusError as e:
        transaction_error_logger.error(f"HTTP status error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to send money")
    except ValueError as e:
        transaction_error_logger.error(f"Value error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to send money")
