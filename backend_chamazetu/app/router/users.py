import logging, uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session


from .. import schemas, utils, oauth2, models
from ..database import get_db

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserResp)
async def create_user(user: schemas.UserBase = Body(...), db: Session = Depends(get_db)):
    user.password = utils.hash_password(user.password)
    new_user = models.User(**user.dict())
    print("-------------------")
    print(new_user)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # send email verification after checking the integrity of the details
    activation_token = await oauth2.create_access_token(data={"sub": new_user.email, "csrf": str(uuid.uuid4())})
    return {"User": [{"id": new_user.id, "email": new_user.email, "activation_code": activation_token, "created_at": new_user.created_at}]}

@router.get("/me")
async def get_user(current_user: models.User = Depends(oauth2.get_current_user), db: Session = Depends(get_db)):
    return {"email": current_user.email}

