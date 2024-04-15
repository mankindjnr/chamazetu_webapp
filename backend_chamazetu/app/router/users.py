import logging, uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session


from .. import schemas, utils, oauth2, models
from ..database import get_db

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserResp)
async def create_user(
    user: schemas.UserBase = Body(...), db: Session = Depends(get_db)
):
    member_check = (
        db.query(models.Member).filter(models.Member.email == user.email).first()
    )
    manager_check = (
        db.query(models.Manager).filter(models.Manager.email == user.email).first()
    )
    if member_check or manager_check:
        raise HTTPException(status_code=400, detail="user already exists")

    dbtable = (user.role).capitalize().strip()

    user.password = utils.hash_password(user.password)
    ModelClass = getattr(
        models, dbtable
    )  # dynamically get the class from the models module
    user_dict = user.dict()
    del user_dict[
        "role"
    ]  # remove the role from the dictionary since we don't have it in the model
    new_user = ModelClass(**user_dict)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # send email verification after checking the integrity of the details
    activation_token = await oauth2.create_access_token(
        data={"sub": new_user.email, "csrf": str(uuid.uuid4())}
    )
    return {
        "User": [
            {
                "id": new_user.id,
                "email": new_user.email,
                "activation_code": activation_token,
                "created_at": new_user.date_joined,
            }
        ]
    }


@router.get("/member")
async def get_user(
    current_user: models.Member = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    return {"email": current_user.email}


@router.get("/manager")
async def get_user(
    current_user: models.Manager = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    return {"email": current_user.email}


# get member id by email
# TODO: might have to repurpose to get managers id by email as well
@router.get("/member/{email}")
async def get_user_by_email(
    email: str,
    db: Session = Depends(get_db),
):
    user = db.query(models.Member).filter(models.Member.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"User_id": user.id}


# get member names by id/email
@router.get("/names/member/{id}")
async def get_member_names_by_id(id: int, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"first_name": member.first_name, "last_name": member.last_name}


# get manager names by id
@router.get("/names/manager/{id}")
async def get_manager_names_by_id(id: int, db: Session = Depends(get_db)):
    manager = db.query(models.Manager).filter(models.Manager.id == id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    return {"first_name": manager.first_name, "last_name": manager.last_name}


# retrieve an active manager/member to esnure the user exists in the database before them to replace a forgotten password - TODO: send email with activation code
@router.get("/{role}/{email}")
async def confirm_user_exists_with_email(
    role: str,
    email: str,
    db: Session = Depends(get_db),
):

    if role == "member":
        user = db.query(models.Member).filter(models.Member.email == email).first()
    elif role == "manager":
        user = db.query(models.Manager).filter(models.Manager.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    return user


@router.put("/{role}/update_password", status_code=status.HTTP_200_OK)
async def update_users_password(
    role: str,
    updated_data: schemas.UpdatePasswordBase = Body(...),
    db: Session = Depends(get_db),
):

    try:
        user_dict = updated_data.dict()
        email = user_dict["email"]
        new_password = utils.hash_password(user_dict["updated_password"])

        if role == "member":
            updated_user = (
                db.query(models.Member).filter(models.Member.email == email).first()
            )
        elif role == "manager":
            updated_user = (
                db.query(models.Manager).filter(models.Manager.email == email).first()
            )

        if updated_user:
            updated_user.password = new_password
            db.commit()
            db.refresh(updated_user)

        return updated_user
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to update password")
