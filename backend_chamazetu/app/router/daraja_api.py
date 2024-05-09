from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List


from .. import schemas, database, utils, oauth2, models

from .stk_push import sendStkPush

router = APIRouter(prefix="/mobile_money", tags=["mobile_money"])


@router.post("/mpesa/stkpush", status_code=status.HTTP_201_CREATED)
def stk_push(
    push_data: schemas.StkPushBase = Body(...),
):
    print("---------stk push---------")
    print(push_data)

    response = sendStkPush(f"254{push_data.phone_number}", push_data.amount)
    print("---------stk response---------")
    return response
