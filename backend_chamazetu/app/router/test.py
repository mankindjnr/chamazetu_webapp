from fastapi import FastAPI, Response, status, HTTPException, Depends, APIRouter
from fastapi.params import Body
from typing import Optional, List
from sqlalchemy import func

from .. import schemas, utils, oauth2, models
from sqlalchemy.orm import Session
from ..database import get_db

router = APIRouter(prefix="/trial")


@router.get("/all")
async def get_trials(
    current_user: models.Member = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    return {"auth": "is working"}
