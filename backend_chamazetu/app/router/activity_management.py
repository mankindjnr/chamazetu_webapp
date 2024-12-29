from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytz, logging
from collections import defaultdict
from sqlalchemy import func, update, and_, table, column, desc

from .date_functions import (
    calculate_custom_interval,
    calculate_monthly_interval,
    calculate_daily_interval,
    calculate_weekly_interval,
    calculate_monthly_same_day_interval,
)
from .members import get_active_activity_by_id
from .chama_and_activity_classes import chamaActivity

from .. import schemas, database, utils, oauth2, models
from app.celery import initiaite_final_fines_transfer_to_manager_wallet

router = APIRouter(prefix="/manage_activities", tags=["activity-management"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")


# manager gets to remove a member from an activity
@router.put("/remove_member_from_activity/{activity_id}/{member_id}")
async def remove_member_from_activity(
    activity_id: int,
    member_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        active_activity = chama_activity.activity_is_active()

        if not activity or not active_activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        if activity.manager_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to perform this action")

        member_exists = db.query(models.activity_user_association).filter(
            and_(
                models.activity_user_association.c.activity_id == activity_id,
                models.activity_user_association.c.user_id == member_id,
                models.activity_user_association.c.user_is_active == True,
            )
        ).first()

        if not member_exists:
            raise HTTPException(status_code=404, detail="Member not found in activity")

        db.query(models.activity_user_association).filter(
            and_(
                models.activity_user_association.c.activity_id == activity_id,
                models.activity_user_association.c.user_id == member_id,
                models.activity_user_association.c.user_is_active == True,
            )
        ).update({models.activity_user_association.c.user_is_active: False})

        db.commit()

        return {"message": "Member removed from activity"}
    except HTTPException as http_exc:
        management_error_logger.error(f"Error removing member from activity: {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Error removing member from activity: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error")


# using a first name and last name, a manger will search for a member and if they are
# found and a member of the activity, we will return their id, email, names and profile picture
# we will rely on two tables, the users table and the activity_user_association table
@router.get("/search_members_in_activity/{activity_id}/{first_name}/{last_name}")
async def search_member_in_activity(
    activity_id: int,
    first_name: str,
    last_name: str,
    db: Session = Depends(database.get_db),
):
    print("======searching for member in activity")
    try:

        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")


        members_in_activity = (
            db.query(models.User)
            .join(models.activity_user_association,
                  models.User.id == models.activity_user_association.c.user_id)
            .filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_is_active == True,
                    models.User.first_name.ilike(f"%{first_name}%"),
                    models.User.last_name.ilike(f"%{last_name}%"),
                )
            )
            .all()
        )
        if not members_in_activity:
            raise HTTPException(status_code=404, detail="No Members found in activity")

        return [
            {
                "id": member.id,
                "email": member.email,
                "first_name": member.first_name,
                "last_name": member.last_name,
                "profile_picture": member.profile_picture,
            }
            for member in members_in_activity
        ]
    except HTTPException as http_exc:
        management_error_logger.error(f"Error searching for member in activity: {http_exc}")
        raise http_exc
    except Exception as exc:
        management_error_logger.error(f"Error searching for member in activity: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error")