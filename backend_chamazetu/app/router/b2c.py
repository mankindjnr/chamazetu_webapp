import os, base64, requests, json
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List
from dotenv import load_dotenv

load_dotenv()


from .. import schemas, database, utils, oauth2, models

from .stk_push import sendStkPush
from .generate_token import generate_access_token

router = APIRouter(prefix="/businesstocustomer", tags=["b2c"])


@router.post("/b2c")
async def b2c_transaction(amount: int, phone_number: str):
    access_token = get_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "InitiatorName": os.getenv("INITIATOR_NAME"),
        "SecurityCredential": os.getenv("SECURITY_CREDENTIAL"),
        "CommandID": "BusinessPayment",
        "Amount": amount,
        "PartyA": os.getenv("B2C_SHORTCODE"),
        "PartyB": 254720090889,
        "Remarks": "TEST remarks",
        "QueueTimeOutURL": "https://chamazetu.com/timeout_url",
        "ResultURL": "https://chamazetu.com/result_url",
        "Occasion": "Occasion",
    }

    response = requests.post(
        os.getenv("B2C_URL"), headers=headers, data=json.dumps(payload)
    )

    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)


# Implement callback endpoints for handling responses
@router.post("/timeout_url")
async def timeout_url(data: dict):
    print("Timeout URL called")
    print(data)
    return {"status": "received"}


@router.post("/result_url")
async def result_url(data: dict):
    print("Result URL called")
    print(data)
    return {"status": "received"}
