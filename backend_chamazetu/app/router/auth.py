from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging, os
from dotenv import load_dotenv
from jose import jwt

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/auth", tags=["Authentication"])

load_dotenv()


# TODO: Introduce try and catch for all the functions or other error handling methods
# member login
@router.post("/login", response_model=schemas.Token)
async def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.email == (user_credentials.username).lower())
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials"
        )

    if not user.is_active or not user.email_verified:
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


@router.post(
    "/refresh",
    response_model=schemas.refreshedToken,
    status_code=status.HTTP_201_CREATED,
)
async def new_access_token(
    token_data: schemas.TokenData = Body(...),
):

    print("**********refreshes************")
    try:
        logging.info(f"token_data: {token_data}")
        new_access_token = await oauth2.create_access_token(
            data={"sub": token_data.username}
        )
        return {"new_access_token": new_access_token, "refreshed_token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# check if a token is valid
@router.post("/isTokenValid", response_model=schemas.TokenData)
async def check_token(
    token_data: schemas.receivedToken = Body(...),
):
    try:
        payload = jwt.decode(
            token_data.token, os.getenv("JWT_SECRET"), algorithms="HS256"
        )
        return True
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# when the token is invalid or expired the route above will raise an exception


# this is for logout, currently not working but everything else is working
# TODO: update the User to correctly logout
@router.post("/logout")
async def logout(current_user: models.Member = Depends(oauth2.get_current_user)):
    token_data = schemas.TokenData(username=current_user.email, expires=0)
    return {"token_data": token_data}
