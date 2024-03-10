from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/auth", tags=["Authentication"])


# TODO: Introduce try and catch for all the functions or other error handling methods
# member login
@router.post("/members/login", response_model=schemas.Token)
async def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.Member)
        .filter(models.Member.email == user_credentials.username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials"
        )

    if not user.is_active or not user.email_verified:
        print("User not active or not verified")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not active or not verified",
        )

    if not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials"
        )

    access_token = await oauth2.create_access_token(data={"sub": user.email})
    refresh_token = await oauth2.create_refresh_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# manager login
@router.post("/managers/login", response_model=schemas.Token)
async def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.Manager)
        .filter(models.Manager.email == user_credentials.username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials"
        )

    if not user.is_active or not user.email_verified:
        print("User not active or not verified")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not active or not verified",
        )

    if not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials"
        )

    access_token = await oauth2.create_access_token(data={"sub": user.email})
    refresh_token = await oauth2.create_refresh_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=schemas.refreshedToken)
async def new_access_token(token_data: schemas.TokenData = Body(...)):
    try:
        logging.info(f"token_data: {token_data}")
        new_access_token = await oauth2.create_access_token(
            data={"sub": token_data.username}
        )
        return {"new_access_token": new_access_token, "refreshed_token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# this is for logout, currently not working but everything else is working
# TODO: update the User to correctly logout
@router.post("/logout")
async def logout(current_user: models.Member = Depends(oauth2.get_current_user)):
    token_data = schemas.TokenData(username=current_user.email, expires=0)
    return {"token_data": token_data}
