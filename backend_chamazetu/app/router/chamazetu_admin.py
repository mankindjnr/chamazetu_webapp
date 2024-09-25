from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session, aliased, joinedload
from datetime import datetime
from typing import List
from uuid import uuid4
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytz, logging
from calendar import monthrange
import calendar
from sqlalchemy import func, update, and_, table, column, desc, select, insert


from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/admin", tags=["admin"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")


# admin will add user to a chama through email
# add current user later to check if they are admin
@router.post("/add_user_to_chama", status_code=status.HTTP_201_CREATED)
async def add_user_to_chama(
    request: schemas.UserChama,
    db: Session = Depends(database.get_db),
):

    try:
        email = request.email
        chama_id = request.chama_id

        user = db.query(models.User).filter(models.User.email == email).first()
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()

        if not user or not chama:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User or Chama not found",
            )

        existing_user_chama = (
            db.query(models.chama_user_association)
            .filter(
                and_(
                    models.chama_user_association.c.user_id == user.id,
                    models.chama_user_association.c.chama_id == chama.id,
                )
            )
            .first()
        )

        if existing_user_chama:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already in chama",
            )

        new_member = models.chama_user_association.insert().values(
            chama_id=chama.id,
            user_id=user.id,
            date_joined=datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0),
            registration_fee_paid=True,
        )
        db.execute(new_member)
        db.commit()

        management_info_logger.info(f"User {user.email} added to chama {chama.name}")
        return {"message": "User added to chama successfully"}
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"Error adding user to chama: {str(e)}")

    # chamzetu admin will add a user to an activity
    # add current user later to check if they are admin


@router.post("/add_user_to_activity", status_code=status.HTTP_201_CREATED)
async def add_user_to_activity(
    request: schemas.UserActivity,
    db: Session = Depends(database.get_db),
):
    print("====================================")
    try:
        email = request.email
        activity_id = request.activity_id

        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        user = db.query(models.User).filter(models.User.email == email).first()

        if not user or not activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User or Activity not found",
            )

        # check if user is already a chama member
        a_chama_member = (
            db.query(models.chama_user_association)
            .filter(
                and_(
                    models.chama_user_association.c.user_id == user.id,
                    models.chama_user_association.c.chama_id == activity.chama_id,
                )
            )
            .first()
        )

        if not a_chama_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not a member of chama",
            )

        an_activity_member = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.user_id == user.id,
                    models.activity_user_association.c.activity_id == activity.id,
                )
            )
            .first()
        )

        if an_activity_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already in activity",
            )

        new_activity_member = insert(models.activity_user_association).values(
            user_id=user.id,
            activity_id=activity.id,
            shares=1,
            share_value=activity.activity_amount,
            date_joined=datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0),
        )
        db.execute(new_activity_member)
        db.commit()
        return {"message": "User added to activity successfully"}
    except HTTPException as http_exc:
        db.rollback()
        management_error_logger.error(
            f"Error adding user to activity: {http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"Error adding user to activity: {str(e)}")
