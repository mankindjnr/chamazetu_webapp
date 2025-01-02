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


@router.put("/swap_rotation_order/{activity_id}", status_code=status.HTTP_200_OK)
async def swapping_rotation_order(
    activity_id: int,
    swap_details: schemas.SwapRotationOrder,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).date()
        chama_activity = chamaActivity(db, activity_id)
        actvity = chama_activity.activity()

        if not actvity:
            raise HTTPException(status_code=404, detail="Activity not found")
        if actvity.manager_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to perform this action")

        cycle_number = chama_activity.current_activity_cycle()
        pulled_order_number = swap_details.pulled_order_number
        pushed_order_number = swap_details.pushed_order_number

        rotation_positions = (
            db.query(models.RotationOrder)
            .filter(
                models.RotationOrder.activity_id == activity_id,
                models.RotationOrder.order_in_rotation.in_([pulled_order_number, pushed_order_number]),
                models.RotationOrder.cycle_number == cycle_number,
                models.RotationOrder.received_amount == 0,
                )
                .with_for_update()
                .all()
        )
        print("==================================")
        print(rotation_positions)

        if len(rotation_positions) != 2:
            raise HTTPException(status_code=404, detail="You can only swap positions that have not received any amount")

        # retrieve the two rotation positions
        pulled_position = next(
            (position for position in rotation_positions if position.order_in_rotation == pulled_order_number), None
        )
        pushed_position = next(
            (position for position in rotation_positions if position.order_in_rotation == pushed_order_number), None
        )

        if not pulled_position or not pushed_position:
            raise HTTPException(status_code=404, detail="Rotation positions not found")


        # checking if the position being pushed is the ongoing recipient
        max_date = (
            db.query(func.max(models.RotatingContributions.rotation_date)).filter(
                models.RotatingContributions.cycle_number == cycle_number,
                models.RotatingContributions.activity_id == activity_id,
                )
                .scalar()
        )

        print("=====max_date=====\n", max_date)

        if pushed_position.receiving_date.date() < today:
            raise HTTPException(status_code=400, detail="You can only swap positions that have not received any amount")

        print("=======dates=======")
        print(pushed_position.receiving_date, max_date, pushed_position.receiving_date == max_date)

        if pushed_position.receiving_date == max_date:
            print("=======dates match=======")
            ongoing_contributions = (
                db.query(models.RotatingContributions).filter(
                    models.RotatingContributions.cycle_number == cycle_number,
                    models.RotatingContributions.activity_id == activity_id,
                    models.RotatingContributions.rotation_date == max_date,
                    )
                    .all()
            )

            # update ongoing contributions to reflect the new recipient and share (pulled position)
            for contribution in ongoing_contributions:
                contribution.recipient_id = pulled_position.recipient_id
                contribution.recipient_share = pulled_position.share_name

        # swap rotation order positions
        pulled_position.order_in_rotation, pushed_position.order_in_rotation = (
            pushed_position.order_in_rotation,
            pulled_position.order_in_rotation,
        )
        #swap rotation order receiving dates
        pulled_position.receiving_date, pushed_position.receiving_date = (
            pushed_position.receiving_date,
            pulled_position.receiving_date,
        )

        db.commit()

        return {"message": "Rotation order swapped successfully"}
    except HTTPException as http_exc:
        db.rollback()
        management_error_logger.error(f"Error swapping rotation order: {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Error swapping rotation order: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search_for_members_by_order_number/{activity_id}")
async def search_by_order_number(
    activity_id: int,
    order_numbers: schemas.SwapRotationOrder,
    db: Session = Depends(database.get_db),
):
    try:
        chama_activity = chamaActivity(db, activity_id)
        active_activity = chama_activity.activity_is_active()

        if not active_activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        cycle_number = chama_activity.merry_go_round_max_cycle()

        rotation_members = (
            db.query(
                models.RotationOrder,
                models.User.profile_picture,
            )
            .join(models.User, models.User.id == models.RotationOrder.recipient_id)
            .filter(
                models.RotationOrder.activity_id == activity_id,
                models.RotationOrder.order_in_rotation.in_([order_numbers.pushed_order_number, order_numbers.pulled_order_number]),
                models.RotationOrder.cycle_number == cycle_number,
                )
                .all()
        )

        if len(rotation_members) != 2:
            raise HTTPException(status_code=404, detail="Order numbers not found, please check the numbers and try again")

        return [
            {
                "id": member.RotationOrder.recipient_id,
                "profile_picture": member.profile_picture,
                "full_name": member.RotationOrder.user_name,
                "share_name": member.RotationOrder.share_name,
                "order_number": member.RotationOrder.order_in_rotation,
            }
            for member in rotation_members
        ]
    except HTTPException as http_exc:
        management_error_logger.error(f"Error searching for members by order number: {http_exc}")
        raise http_exc
    except Exception as exc:
        management_error_logger.error(f"Error searching for members by order number: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error")