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

router = APIRouter(prefix="/mobile_money", tags=["mobile_money"])


@router.post("/mpesa/stkpush", status_code=status.HTTP_201_CREATED)
def stk_push(
    push_data: schemas.StkPushBase = Body(...),
):
    print("---------stk push---------")
    print(push_data)

    response = sendStkPush(
        f"254{push_data.phone_number}",
        push_data.amount,
        push_data.recipient,
        push_data.description,
    )
    return response


@router.get("/mpesa/stkpush/status/{checkout_request_id}")
def stk_push_status(
    checkout_request_id: str,
):
    print("---------stk push status---------")
    query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        (os.getenv("SHORTCODE") + os.getenv("PASSKEY") + timestamp).encode()
    ).decode()

    query_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {generate_access_token()}",
    }

    query_payload = {
        "BusinessShortCode": os.getenv("SHORTCODE"),
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    print("---status---")
    print(query_headers)
    print()
    print(query_payload)

    try:
        response = requests.post(query_url, headers=query_headers, json=query_payload)
        response.raise_for_status()  # Raise exception for non-2xx status codes
        response_data = response.json()
        print(response_data)

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

        # call a function to refresh access token and send it back to the client
        return {"message": message, "queryResponse": response_data}
    except requests.exceptions.RequestException as e:
        print("Request error:", str(e))
        raise HTTPException(status_code=400, detail="Failed to query stk push status")
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", str(e))
        raise HTTPException(status_code=400, detail="Failed to query stk push status")
