from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from decouple import config

from . import schemas, database, models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = config('JWT_SECRET')
ALGORITHM = config('JWT_ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = int(config('JWT_EXPIRE_MINUTES'))
JWT_REFRESH_EXPIRE_DAYS = int(config('JWT_REFRESH_EXPIRE_DAYS'))


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
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
        return token_data
    except JWTError:
        raise credentials_exception

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    token = await verify_access_token(token, credentials_exception)
    user = db.query(models.User).filter(models.User.email == token.username).first()
    if user is None:
        raise credentials_exception
    return user