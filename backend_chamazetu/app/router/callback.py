from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Request
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List


from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/callback", tags=["callback"])


@router.post("/")
async def mpesa_callback(request: Request):
    payload = await request.json()
    # Process the callback payload here
    return {"ResultCode": 0, "ResultDesc": "Success"}
