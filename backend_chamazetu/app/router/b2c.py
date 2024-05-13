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


# @router.post("/payment", response_model=schemas.PaymentResponse)
# def b2c_payment(
#     request: schemas.PaymentRequest, db: Session = Depends(database.get_db)
# ):
#     access_token = generate_access_token()

#     headers = {
#         "content-type": "application/json",
#         "Authorization": f"Bearer {access_token}",
#     }

# payload = {
#     "InitiatorName": os.getenv("INITIATOR_NAME"),
#     "SecurityCredential": os.getenv("SECURITY_CREDENTIAL"),
#     "CommandID": "BusinessPayment",
#     "Amount": request.amount,
#     "PartyA": os.getenv("SHORTCODE"),
#     "PartyB": request.phone_number,
#     "Remarks": request.remarks,
#     "QueueTimeOutURL": os.getenv("QUEUE_TIMEOUT_URL"),
#     "ResultURL": os.getenv("RESULT_URL"),
#     "Occasion": request.occasion
# }

# return 0
