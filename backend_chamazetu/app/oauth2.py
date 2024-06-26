import logging, os
from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from . import schemas, database, models

load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES"))
JWT_REFRESH_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS"))


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
    print(token)
    if not token:
        raise credentials_exception

    if not token.startswith("Bearer"):
        raise credentials_exception
    if not SECRET_KEY or not ALGORITHM:
        raise credentials_exception
    try:
        payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
        print(payload)
    except ExpiredSignatureError:
        raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    except Exception as e:
        raise credentials_exception

    username: str = payload.get("sub")
    role: str = payload.get("role")
    if not username or not role:
        raise credentials_exception

    # check if the user exists in the database

    token_data = schemas.TokenData(username=username, role=role)
    return token_data


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)
):
    print("===get_current_user===")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = await verify_access_token(token, credentials_exception)
    role = token.role
    Model = getattr(models, role.capitalize())
    user = db.query(Model).filter(Model.email == token.username).first()
    if user is None:
        print("===user not found===")
        raise credentials_exception
    return user
