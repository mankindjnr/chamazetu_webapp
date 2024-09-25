import logging, uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from typing import Union
from zoneinfo import ZoneInfo
from datetime import datetime
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, utils, oauth2, models
from ..database import get_db

router = APIRouter(prefix="/users", tags=["Users"])

nairobi_tz = ZoneInfo("Africa/Nairobi")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserResp)
async def create_user(
    user: schemas.UserBase = Body(...), db: Session = Depends(get_db)
):

    # email to lowercase
    try:
        email = (user.email).lower()
        new_user = db.query(models.User).filter(models.User.email == email).first()
        print("new user", new_user)

        if new_user:
            raise HTTPException(status_code=400, detail="user already exists")

        user.password = utils.hash_password(user.password)
        user_dict = user.dict()
        user_dict["profile_picture"] = (
            "https://chamazetu-web.s3.eu-north-1.amazonaws.com/profile_pictures/tree_grow_money.jpg"
        )
        date = datetime.now(nairobi_tz).replace(tzinfo=None)
        user_dict["date_joined"] = date
        user_dict["updated_at"] = date

        new_user = models.User(**user_dict)
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
    except Exception as e:
        print("=====sgnup error=====")
        print(e)
        db.rollback()


# update member email to true after email verification
@router.put("/email_verification/{uid}", status_code=status.HTTP_200_OK)
async def update_email_verification(
    uid: int,
    user_email: schemas.UserEmailActvationBase = Body(...),
    db: Session = Depends(get_db),
):
    email = (user_email.dict()["user_email"]).lower()
    user = (
        db.query(models.User)
        .filter(and_(models.User.id == uid, models.User.email == email))
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
    email = (user_email.dict()["user_email"]).lower()
    user = (
        db.query(models.User)
        .filter(and_(models.User.id == uid, models.User.email == user_email.user_email))
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
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    return {"email": current_user.email}


@router.get("/manager")
async def get_user(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    return {"email": current_user.email}


#      ======================might switch back to email instead of id=======================
# get member/manager id by email
@router.get("/profile_picture")
async def get_user_by_email(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    user = db.query(models.User).filter(models.User.id == current_user.id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"User_id": user.id, "profile_picture": user.profile_picture}


# get user id
@router.get("/id/{email}")
async def get_user_id_by_email(
    email: str,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"User_id": user.id}


# get member names by id
@router.get("/names/{user_id}")
async def get_member_names_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"first_name": user.first_name, "last_name": user.last_name}


# get manager/member phone_number by id
@router.get("/phone_number/{id}")
async def get_phone_number_by_id(id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"phone_number": user.phone_number}


# get user email by id
@router.get("/email/{user_id}")
async def get_email_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"email": user.email}


# get manager names by id
@router.get("/names/manager/{id}")
async def get_manager_names_by_id(id: int, db: Session = Depends(get_db)):
    manager = db.query(models.User).filter(models.User.id == id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    return {"first_name": manager.first_name, "last_name": manager.last_name}


# retrieve an active manager/member to esnure the user exists in the database before them to replace a forgotten password - TODO: send email with activation code
@router.get("/{email}")
async def confirm_user_exists_with_email(
    email: str,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == email.lower()).first()

    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    return user


# resetting password - forgotten password
@router.put("/update_password", status_code=status.HTTP_200_OK)
async def update_users_password(
    updated_data: schemas.UpdatePasswordBase = Body(...),
    db: Session = Depends(get_db),
):

    try:
        user_dict = updated_data.dict()
        email = user_dict["email"]
        new_password = utils.hash_password(user_dict["updated_password"])

        updated_user = db.query(models.User).filter(models.User.email == email).first()

        if updated_user:
            updated_user.password = new_password
            db.commit()
            db.refresh(updated_user)

        return updated_user
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to update password")


# get users full_profile
@router.get("/full_profile/{id}", status_code=status.HTTP_200_OK)
async def get_user_full_profile(
    id: int,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == id).first()
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
@router.get("/profile_picture", status_code=status.HTTP_200_OK)
async def get_user_profile_picture(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == current_user.id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"profile_picture": user.profile_picture}


# changing password
@router.put("/change_password", status_code=status.HTTP_201_CREATED)
async def change_password(
    password_data: schemas.ChangePasswordBase = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
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
    "/update_phone_number",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_member_phone_number(
    phone_number_data: schemas.PhoneNumberBase = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        phone_number_dict = phone_number_data.dict()
        new_phone_number = phone_number_dict["phone_number"]

        user = db.query(models.User).filter(models.User.id == current_user.id).first()

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
    "/update_twitter_handle",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_twitter(
    twitter_data: schemas.TwitterBase = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        twitter_dict = twitter_data.dict()
        new_twitter = twitter_dict["twitter"]

        user = db.query(models.User).filter(models.User.id == current_user.id).first()

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
    "/update_facebook_handle",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_member_facebook(
    facebook_data: schemas.FacebookBase = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        facebook_dict = facebook_data.dict()
        new_facebook = facebook_dict["facebook"]

        user = db.query(models.User).filter(models.User.id == current_user.id).first()

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
    "/update_linkedin_handle",
    status_code=status.HTTP_200_OK,
    response_model=schemas.SuccessBase,
)
async def update_member_linkedin(
    linkedin_data: schemas.LinkedinBase = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        linkedin_dict = linkedin_data.dict()
        new_linkedin = linkedin_dict["linkedin"]

        user = db.query(models.User).filter(models.User.id == current_user.id).first()
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


# checking users active role by checking if he has joined a chama or created one
@router.get("/active_role/{email}", status_code=status.HTTP_200_OK)
async def get_active_role(
    email: str,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not being found")

    chamas_managing = (
        db.query(models.Chama).filter(models.Chama.manager_id == user.id).all()
    )
    # check if the user has joined a chama from the chama_user_association table
    chama_joined = (
        db.query(models.User).filter(models.User.id == user.id).first().chamas
    )

    if chamas_managing and not chama_joined:
        return {"active_role": "manager"}

    return {"active_role": "member"}
