import logging
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from decouple import config

from . import schemas, database, models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = config("JWT_SECRET")
ALGORITHM = config("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(config("JWT_EXPIRE_MINUTES"))
JWT_REFRESH_EXPIRE_DAYS = int(config("JWT_REFRESH_EXPIRE_DAYS"))


async def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_access_token(token: str, credentials_exception):
    print("------verifying access token--------")
    if not token:
        raise credentials_exception

    if not token.startswith("Bearer"):
        raise credentials_exception
    print("---------aecret key check-------------")
    if not SECRET_KEY or not ALGORITHM:
        raise credentials_exception
    print("---------try key check-------------")
    try:
        payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        print("------payload--------")
        print(payload)
    except ExpiredSignatureError:
        print("------expired token--------")
        raise credentials_exception
    except InvalidTokenError:
        print("------invalid token--------")
        raise credentials_exception
    except Exception as e:
        print("------unknown error--------")
        raise credentials_exception

    username: str = payload.get("sub")
    role: str = payload.get("role")
    print("------username and role--------")
    if not username or not role:
        raise credentials_exception

    # check if the user exists in the database

    token_data = schemas.TokenData(username=username, role=role)
    return token_data


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)
):
    print("------checking for current user--------")
    print(token)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    print("------checking for current user--------")
    token = await verify_access_token(token, credentials_exception)
    print("-----the token in question\n", token)
    role = token.role
    Model = getattr(models, role.capitalize())
    user = db.query(Model).filter(Model.email == token.username).first()
    if user is None:
        raise credentials_exception
    return user
