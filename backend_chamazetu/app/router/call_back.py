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

router = APIRouter(prefix="/callback", tags=["mobile_money"])


@router.post("/")
def c2b_callback(call_back_data):
    print(
        "---===================================---c2b callback-=====================================---"
    )
    print(call_back_data.dict())
    return {"message": "c2b callback"}
