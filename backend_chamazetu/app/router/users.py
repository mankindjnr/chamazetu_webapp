import logging, uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from typing import Union
from sqlalchemy import func, update, and_, table, column, desc

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


# update member email to true after email verification
@router.put("/member_email_verification/{uid}", status_code=status.HTTP_200_OK)
async def update_email_verification(
    uid: int,
    user_email: schemas.UserEmailActvationBase = Body(...),
    db: Session = Depends(get_db),
):
    email = user_email.dict()["user_email"]
    user = (
        db.query(models.Member)
        .filter(and_(models.Member.id == uid, models.Member.email == email))
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = True
    user.is_active = True
    db.commit()
    db.refresh(user)
    return {"message": "Email verified successfully"}


# update manager email to true after email verification
@router.put("/manager_email_verification/{uid}", status_code=status.HTTP_200_OK)
async def update_email_verification(
    uid: int,
    user_email: schemas.UserEmailActvationBase = Body(...),
    db: Session = Depends(get_db),
):
    email = user_email.dict()["user_email"]
    user = (
        db.query(models.Manager)
        .filter(
            and_(
                models.Manager.id == uid, models.Manager.email == user_email.user_email
            )
        )
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified = True
    user.is_active = True
    db.commit()
    db.refresh(user)
    return {"message": "Email verified successfully"}


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


# get member/manager id by email
# TODO: might have to repurpose to get managers id by email as well
@router.get("/{role}/{email}")
async def get_user_by_email(
    role: str,
    email: str,
    db: Session = Depends(get_db),
):
    user = None
    if role == "member":
        user = db.query(models.Member).filter(models.Member.email == email).first()
    elif role == "manager":
        user = db.query(models.Manager).filter(models.Manager.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"User_id": user.id, "profile_picture": user.profile_picture}


# get member names by id
@router.get("/names/member/{id}")
async def get_member_names_by_id(id: int, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"first_name": member.first_name, "last_name": member.last_name}


# get manager/member phone_number by id
@router.get("/phone_number/{role}/{id}")
async def get_phone_number_by_id(id: int, role: str, db: Session = Depends(get_db)):
    if role == "member":
        user = db.query(models.Member).filter(models.Member.id == id).first()
    elif role == "manager":
        user = db.query(models.Manager).filter(models.Manager.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"phone_number": user.phone_number}


# get member email by id
@router.get("/email/{role}/{id}")
async def get_email_by_id(id: int, role: str, db: Session = Depends(get_db)):
    if role == "member":
        user = db.query(models.Member).filter(models.Member.id == id).first()
    elif role == "manager":
        user = db.query(models.Manager).filter(models.Manager.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": user.email}


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


# resetting password - forgotten password
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


# get users full_profile
@router.get("/full_profile/{role}/{id}", status_code=status.HTTP_200_OK)
async def get_user_full_profile(
    role: str,
    id: int,
    db: Session = Depends(get_db),
):
    if role == "member":
        user = db.query(models.Member).filter(models.Member.id == id).first()
    elif role == "manager":
        user = db.query(models.Manager).filter(models.Manager.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user.id,
        "profile_image": user.profile_picture,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone_number": user.phone_number or "N/A",
        "twitter_handle": user.twitter or "N/A",
        "facebook_handle": user.facebook or "N/A",
        "linkedin_handle": user.linkedin or "N/A",
        "active_user": user.is_active,
        "date_joined": user.date_joined,
    }

    # "profile_picture": user.profile_picture,


# retrive a users profile picture
@router.get("/profile_picture/{role}", status_code=status.HTTP_200_OK)
async def get_user_profile_picture(
    role: str,
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
    db: Session = Depends(get_db),
):
    user = None
    if role == "member":
        user = (
            db.query(models.Member).filter(models.Member.id == current_user.id).first()
        )
    elif role == "manager":
        user = (
            db.query(models.Manager)
            .filter(models.Manager.id == current_user.id)
            .first()
        )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"profile_picture": user.profile_picture}


# changing password
@router.put("/{role}/change_password", status_code=status.HTTP_201_CREATED)
async def change_password(
    role: str,
    password_data: schemas.ChangePasswordBase = Body(...),
    db: Session = Depends(get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        print("we are changig password========")
        user_dict = password_data.dict()
        old_password = user_dict["old_password"]
        new_password = user_dict["new_password"]

        if not utils.verify_password(old_password, current_user.password):
            raise HTTPException(status_code=400, detail="Incorrect old password")

        current_user.password = utils.hash_password(new_password)
        db.commit()
        db.refresh(current_user)

        return {"message": "Password changed successfully"}
    except Exception as e:
        print("===============password change error================")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to change password")


# update members table with new phone number
@router.put(
    "/{role}/update_phone_number",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_member_phone_number(
    role: str,
    phone_number_data: schemas.PhoneNumberBase = Body(...),
    db: Session = Depends(get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        phone_number_dict = phone_number_data.dict()
        new_phone_number = phone_number_dict["phone_number"]

        user = None

        if role == "member":
            user = (
                db.query(models.Member)
                .filter(models.Member.id == current_user.id)
                .first()
            )
        elif role == "manager":
            user = (
                db.query(models.Manager)
                .filter(models.Manager.id == current_user.id)
                .first()
            )

        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        user.phone_number = new_phone_number
        db.commit()
        db.refresh(user)

        return {"message": "Phone number updated successfully"}

    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Failed to update members phone number"
        )


# update members table with twitter
@router.put(
    "/{role}/update_twitter_handle",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_twitter(
    role: str,
    twitter_data: schemas.TwitterBase = Body(...),
    db: Session = Depends(get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        twitter_dict = twitter_data.dict()
        new_twitter = twitter_dict["twitter"]

        user = None
        if role == "member":
            user = (
                db.query(models.Member)
                .filter(models.Member.id == current_user.id)
                .first()
            )
        elif role == "manager":
            user = (
                db.query(models.Manager)
                .filter(models.Manager.id == current_user.id)
                .first()
            )

        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        user.twitter = new_twitter
        db.commit()
        db.refresh(user)

        return {"message": "Twitter updated successfully"}

    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to update user's twitter")


# update members table with facebook
@router.put(
    "/{role}/update_facebook_handle",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_member_facebook(
    role: str,
    facebook_data: schemas.FacebookBase = Body(...),
    db: Session = Depends(get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        facebook_dict = facebook_data.dict()
        new_facebook = facebook_dict["facebook"]

        user = None

        if role == "member":
            user = (
                db.query(models.Member)
                .filter(models.Member.id == current_user.id)
                .first()
            )
        elif role == "manager":
            user = (
                db.query(models.Manager)
                .filter(models.Manager.id == current_user.id)
                .first()
            )

        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        user.facebook = new_facebook
        db.commit()
        db.refresh(user)

        return {"message": "Facebook updated successfully"}

    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to update user's facebook")


# update members table with linkedin
@router.put(
    "/{role}/update_linkedin_handle",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_member_linkedin(
    role: str,
    linkedin_data: schemas.LinkedinBase = Body(...),
    db: Session = Depends(get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        linkedin_dict = linkedin_data.dict()
        new_linkedin = linkedin_dict["linkedin"]

        user = None

        if role == "member":
            user = (
                db.query(models.Member)
                .filter(models.Member.id == current_user.id)
                .first()
            )
        elif role == "manager":
            user = (
                db.query(models.Manager)
                .filter(models.Manager.id == current_user.id)
                .first()
            )

        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        user.linkedin = new_linkedin
        db.commit()
        db.refresh(user)

        return {"message": "Linkedin updated successfully"}

    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to update user's linkedin")
