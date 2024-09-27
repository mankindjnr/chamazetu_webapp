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

router = APIRouter(prefix="/activities", tags=["activities"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")


# create an activity
@router.post(
    "/", response_model=schemas.CreateActivityResp, status_code=status.HTTP_201_CREATED
)
async def create_activity(
    activity: schemas.ActivityBase,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity_data = activity.dict()
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        activity_data["creation_date"] = today
        activity_data["updated_at"] = today
        activity_data["manager_id"] = current_user.id
        # convert the activity date to datetime object
        activity_data["last_joining_date"] = datetime.strptime(
            activity_data["last_joining_date"], "%Y-%m-%d"
        )
        activity_data["first_contribution_date"] = datetime.strptime(
            activity_data["first_contribution_date"], "%Y-%m-%d"
        )

        # wrap in a transaction to ensure atomicity
        with db.begin_nested():
            new_activity = models.Activity(**activity_data)
            db.add(new_activity)
            db.flush()  # flush to get the id of the newly created activity

            # add the manager as a member of the activity
            activity_contribution = {
                "chama_id": activity_data["chama_id"],
                "activity_id": new_activity.id,
                "activity_title": activity_data["activity_title"],
                "activity_type": activity_data["activity_type"],
                "frequency": activity_data["frequency"],
                "previous_contribution_date": activity_data["last_joining_date"],
                "next_contribution_date": activity_data["first_contribution_date"],
            }

            new_activity_contribution = models.ActivityContributionDate(
                **activity_contribution
            )
            db.add(new_activity_contribution)

            # create an account for the activity
            new_activity_account = models.Activity_Account(
                activity_id=new_activity.id, account_balance=0.0
            )
            db.add(new_activity_account)

        db.commit()
        # TODO:for mandatory activities, remember to add all members to the activity_members table(many to many)-THINK ABOUT IT
        return {"status": "success", "message": "Activity created successfully"}
    except HTTPException as e:
        db.rollback()
        management_error_logger.error(f"Failed to create activity: {e}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"Failed to create activity: {e}")
        raise HTTPException(status_code=400, detail="Failed to create activity")


# retrieve an activity by id as a manager
@router.get(
    "/manager/{activity_id}",
    response_model=schemas.ActivityResp,
    status_code=status.HTTP_200_OK,
)
async def get_activity_by_id(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        account = (
            db.query(models.Activity_Account.account_balance)
            .filter(models.Activity_Account.activity_id == activity_id)
            .scalar()
        )

        if not account:
            account = 0.0

        activity = {
            "chama_id": activity.chama_id,
            "activity_name": activity.activity_title,
            "activity_type": activity.activity_type,
            "activity_amount": activity.activity_amount,
            "activity_balance": account,
            "activity_id": activity,
        }

        return activity
    except HTTPException as e:
        management_error_logger.error(f"Failed to get activity by id: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get activity by id: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve activity by id")


# retrieve all activities for any user in a chama
@router.get(
    "/chama/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_all_activities(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        # TODO: chanage <= to >=
        activities = (
            db.query(models.Activity)
            .filter(
                and_(
                    models.Activity.chama_id == chama_id,
                    models.Activity.last_joining_date
                    <= datetime.now(nairobi_tz).date(),
                )
            )
            .all()
        )

        activities_list = []
        for activity in activities:
            activity = {
                "name": activity.activity_title,
                "type": activity.activity_type,
                "amount": activity.activity_amount,
                "frequency": activity.frequency,
                "interval": activity.interval,
                "contribution_day": activity.contribution_day,
                "first_contribution_date": activity.first_contribution_date.strftime(
                    "%d-%B-%Y"
                ),
                "description": activity.activity_description,
                "activity_id": activity.id,
            }
            activities_list.append(activity)
        return activities_list
    except HTTPException as e:
        management_error_logger.error(f"Failed to get all activities: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get all activities: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve all activities")


# join a cham activity
@router.post(
    "/join/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def join_activity(
    activity_id: int,
    num_of_shares: schemas.JoinActivityBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        # check if the user is already a member of this chama frm the chama_user_association table
        a_chama_member = (
            db.query(models.chama_user_association)
            .filter(
                and_(
                    models.chama_user_association.c.user_id == current_user.id,
                    models.chama_user_association.c.chama_id == activity.chama_id,
                )
            )
            .first()
        )

        if not a_chama_member:
            raise HTTPException(
                status_code=400, detail="You are not a member of this chama"
            )

        # check if the user is already a member of this activity using teh activity_user_association table
        an_activity_member = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.user_id == current_user.id,
                    models.activity_user_association.c.activity_id == activity_id,
                )
            )
            .first()
        )

        if an_activity_member:
            raise HTTPException(
                status_code=400, detail="You are already a member of this activity"
            )

        # add the user to the activity_user_association table
        new_activity_member = insert(models.activity_user_association).values(
            user_id=current_user.id,
            activity_id=activity_id,
            shares=num_of_shares.shares,
            share_value=activity.activity_amount,
            date_joined=datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0),
        )
        db.execute(new_activity_member)
        db.commit()
        return {"status": "success", "message": "You have successfully joined"}
    except HTTPException as e:
        management_error_logger.error(f"Failed to join activity: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to join activity: {e}")
        raise HTTPException(status_code=400, detail="Failed to join activity")


# check if a user is a member of an activity
@router.get(
    "/{activity_id}/member",
    status_code=status.HTTP_200_OK,
)
async def check_activity_membership(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        # check if the user is already a member of this activity using the activity_user_association table
        an_activity_member = (
            db.query(models.activity_user_association)
            .filter(
                and_(
                    models.activity_user_association.c.user_id == current_user.id,
                    models.activity_user_association.c.activity_id == activity_id,
                )
            )
            .first()
        )

        if not an_activity_member:
            return {
                "status": "success",
                "member_in_activity": False,
                "message": "You are not a member of this activity",
            }
        return {
            "status": "success",
            "member_in_activity": True,
            "message": "You are a member of this activity",
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to check activity membership: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to check activity membership: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to check activity membership"
        )


# get a merry go round activity
@router.get(
    "/merry-go-round/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_merry_go_round_activity(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        # fetch activity and eager load related accout and user data in one go
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        # check if the activity is a merry go round activity
        if activity.activity_type != "merry-go-round":
            raise HTTPException(
                status_code=400, detail="This is not a merry go round activity"
            )

        # pre-fetch wallet balance, unpaid fines, and other key data in a single call
        wallet_balance = (
            db.query(models.User.wallet_balance)
            .filter(models.User.id == current_user.id)
            .scalar()
            or 0.0
        )

        unpaid_fines = (
            db.query(func.coalesce(func.sum(models.ActivityFine.expected_repayment), 0))
            .filter(
                models.ActivityFine.user_id == current_user.id,
                models.ActivityFine.activity_id == activity_id,
                models.ActivityFine.is_paid == False,
            )
            .scalar()
            or 0
        )

        account_balance = (
            db.query(models.Activity_Account.account_balance)
            .filter(models.Activity_Account.activity_id == activity_id)
            .scalar()
            or 0.0
        )

        ## sum todays contributions to this activity
        today = datetime.now(nairobi_tz).date()
        today_contributions = (
            db.query(func.coalesce(func.sum(models.ActivityTransaction.amount), 0))
            .filter(
                models.ActivityTransaction.activity_id == activity_id,
                models.ActivityTransaction.user_id == current_user.id,
                models.ActivityTransaction.transaction_type == "contribution",
                models.ActivityTransaction.transaction_completed == True,
                func.date(models.ActivityTransaction.transaction_date) == today,
            )
            .scalar()
            or 0
        )

        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )
        prev_contribution_date = (
            db.query(models.ActivityContributionDate.previous_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )

        if not next_contribution_date or not prev_contribution_date:
            raise HTTPException(
                status_code=400, detail="Failed to get contribution dates"
            )

        prev_sunday = today - timedelta(days=today.weekday() + 1)
        ActivityUserAssoc = aliased(models.activity_user_association)

        if activity.frequency in ["daily", "weekly"]:
            weekly_contributions = (
                db.query(
                    models.ActivityTransaction.user_id,
                    models.ActivityTransaction.amount,
                    models.ActivityTransaction.transaction_date,
                    models.User.first_name,
                    models.User.last_name,
                    ActivityUserAssoc.c.shares,
                )
                .join(models.User, models.User.id == models.ActivityTransaction.user_id)
                .join(
                    ActivityUserAssoc,
                    and_(
                        ActivityUserAssoc.c.user_id
                        == models.ActivityTransaction.user_id,
                        ActivityUserAssoc.c.activity_id
                        == models.ActivityTransaction.activity_id,
                    ),
                )
                .filter(
                    models.ActivityTransaction.activity_id
                    == ActivityUserAssoc.c.activity_id,
                )
                .filter(
                    models.ActivityTransaction.activity_id == activity_id,
                    models.ActivityTransaction.transaction_type.in_(
                        ["contribution", "late contribution"]
                    ),
                    models.ActivityTransaction.transaction_completed == True,
                    func.date(models.ActivityTransaction.transaction_date)
                    > prev_contribution_date,
                    func.date(models.ActivityTransaction.transaction_date) <= today,
                )
                .all()
            )

            weekly_contributions_list = [
                {
                    "user_id": contribution.user_id,
                    "amount": contribution.amount,
                    "date": contribution.transaction_date.date(),
                    "first_name": contribution.first_name,
                    "last_name": contribution.last_name,
                    "shares": contribution.shares,
                }
                for contribution in weekly_contributions
            ]
        elif activity.frequency in ["monthly", "interval"]:
            weekly_contributions = (
                db.query(
                    models.ActivityTransaction.user_id,
                    models.ActivityTransaction.amount,
                    models.ActivityTransaction.transaction_date,
                    models.User.first_name,
                    models.User.last_name,
                    ActivityUserAssoc.c.shares,
                )
                .join(models.User, models.User.id == models.ActivityTransaction.user_id)
                .join(
                    ActivityUserAssoc,
                    and_(
                        ActivityUserAssoc.c.user_id
                        == models.ActivityTransaction.user_id,
                        ActivityUserAssoc.c.activity_id
                        == models.ActivityTransaction.activity_id,
                    ),
                )
                .filter(
                    models.ActivityTransaction.activity_id
                    == ActivityUserAssoc.c.activity_id,
                )
                .filter(
                    models.ActivityTransaction.activity_id == activity_id,
                    models.ActivityTransaction.transaction_type.in_(
                        ["contribution", "late contribution"]
                    ),
                    models.ActivityTransaction.transaction_completed == True,
                    func.date(models.ActivityTransaction.transaction_date)
                    > prev_sunday,
                    func.date(models.ActivityTransaction.transaction_date) <= today,
                )
                .all()
            )

            weekly_contributions_list = [
                {
                    "user_id": contribution.user_id,
                    "amount": contribution.amount,
                    "date": contribution.transaction_date.date(),
                    "first_name": contribution.first_name,
                    "last_name": contribution.last_name,
                    "shares": contribution.shares,
                }
                for contribution in weekly_contributions
            ]

        activity_data = {
            "activity_id": activity.id,
            "activity_name": activity.activity_title,
            "activity_frequency": activity.frequency,
            "activity_type": activity.activity_type,
            "activity_amount": activity.activity_amount,
            "activity_balance": account_balance,
            "wallet_balance": wallet_balance,
            "unpaid_fines": unpaid_fines,
            "next_contribution_date": next_contribution_date.strftime("%d-%B-%Y"),
            "today_contributions": today_contributions,
            "weekly_contributions": weekly_contributions_list,
        }

        return activity_data

    except HTTPException as e:
        management_error_logger.error(f"Failed to get merry go round activity: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get merry go round activity: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to retrieve merry go round activity"
        )


# ======= activity endpoint=======
# e.g welfare, investment, saving - same structure compared to merry go round
@router.get(
    "/activity_data/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_activity_data(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        # fetch activity and eager load related accout and user data in one go
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        # pre-fetch wallet balance, unpaid fines, and other key data in a single call
        wallet_balance = (
            db.query(models.User.wallet_balance)
            .filter(models.User.id == current_user.id)
            .scalar()
            or 0.0
        )

        unpaid_fines = (
            db.query(func.coalesce(func.sum(models.ActivityFine.expected_repayment), 0))
            .filter(
                models.ActivityFine.user_id == current_user.id,
                models.ActivityFine.activity_id == activity_id,
                models.ActivityFine.is_paid == False,
            )
            .scalar()
            or 0
        )

        account_balance = (
            db.query(models.Activity_Account.account_balance)
            .filter(models.Activity_Account.activity_id == activity_id)
            .scalar()
            or 0.0
        )

        ## sum todays contributions to this activity
        today = datetime.now(nairobi_tz).date()
        today_contributions = (
            db.query(func.coalesce(func.sum(models.ActivityTransaction.amount), 0))
            .filter(
                models.ActivityTransaction.activity_id == activity_id,
                models.ActivityTransaction.transaction_type == "contribution",
                models.ActivityTransaction.transaction_completed == True,
                func.date(models.ActivityTransaction.transaction_date) == today,
            )
            .scalar()
            or 0
        )

        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )
        if not next_contribution_date:
            raise HTTPException(
                status_code=400, detail="Failed to get next contribution date"
            )

        prev_contribution_date = (
            db.query(models.ActivityContributionDate.previous_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )

        prev_sunday = today - timedelta(days=today.weekday() + 1)
        ActivityUserAssoc = aliased(models.activity_user_association)

        if activity.frequency in ["daily", "weekly"]:
            weekly_contributions = (
                db.query(
                    models.ActivityTransaction.user_id,
                    models.ActivityTransaction.amount,
                    models.ActivityTransaction.transaction_date,
                    models.User.first_name,
                    models.User.last_name,
                    ActivityUserAssoc.c.shares,
                )
                .join(models.User, models.User.id == models.ActivityTransaction.user_id)
                .join(
                    ActivityUserAssoc,
                    and_(
                        ActivityUserAssoc.c.user_id
                        == models.ActivityTransaction.user_id,
                        ActivityUserAssoc.c.activity_id
                        == models.ActivityTransaction.activity_id,
                    ),
                )
                .filter(
                    models.ActivityTransaction.activity_id
                    == ActivityUserAssoc.c.activity_id,
                )
                .filter(
                    models.ActivityTransaction.activity_id == activity_id,
                    models.ActivityTransaction.transaction_type.in_(
                        ["contribution", "late contribution"]
                    ),
                    models.ActivityTransaction.transaction_completed == True,
                    func.date(models.ActivityTransaction.transaction_date)
                    > prev_contribution_date,
                    func.date(models.ActivityTransaction.transaction_date) <= today,
                )
                .all()
            )

            weekly_contributions_list = [
                {
                    "user_id": contribution.user_id,
                    "amount": contribution.amount,
                    "date": contribution.transaction_date.date(),
                    "first_name": contribution.first_name,
                    "last_name": contribution.last_name,
                    "shares": contribution.shares,
                }
                for contribution in weekly_contributions
            ]
        elif activity.frequency in ["monthly", "interval"]:
            weekly_contributions = (
                db.query(
                    models.ActivityTransaction.user_id,
                    models.ActivityTransaction.amount,
                    models.ActivityTransaction.transaction_date,
                    models.User.first_name,
                    models.User.last_name,
                    ActivityUserAssoc.c.shares,
                )
                .join(models.User, models.User.id == models.ActivityTransaction.user_id)
                .join(
                    ActivityUserAssoc,
                    and_(
                        ActivityUserAssoc.c.user_id
                        == models.ActivityTransaction.user_id,
                        ActivityUserAssoc.c.activity_id
                        == models.ActivityTransaction.activity_id,
                    ),
                )
                .filter(
                    models.ActivityTransaction.activity_id
                    == ActivityUserAssoc.c.activity_id,
                )
                .filter(
                    models.ActivityTransaction.activity_id == activity_id,
                    models.ActivityTransaction.transaction_type.in_(
                        ["contribution", "late contribution"]
                    ),
                    models.ActivityTransaction.transaction_completed == True,
                    func.date(models.ActivityTransaction.transaction_date)
                    > prev_sunday,
                    func.date(models.ActivityTransaction.transaction_date) <= today,
                    # TODO: check is setting to explicitly to saturday is better or just previos 7 days including today and then chnage the receiving function to accomodate it
                )
                .all()
            )

            weekly_contributions_list = [
                {
                    "user_id": contribution.user_id,
                    "amount": contribution.amount,
                    "date": contribution.transaction_date.date(),
                    "first_name": contribution.first_name,
                    "last_name": contribution.last_name,
                    "shares": contribution.shares,
                }
                for contribution in weekly_contributions
            ]

        activity_data = {
            "activity_id": activity.id,
            "activity_name": activity.activity_title,
            "activity_type": activity.activity_type,
            "activity_frequency": activity.frequency,
            "activity_amount": activity.activity_amount,
            "activity_balance": account_balance,
            "wallet_balance": wallet_balance,
            "unpaid_fines": unpaid_fines,
            "previous_contribution_date": prev_contribution_date.strftime("%d-%B-%Y"),
            "next_contribution_date": next_contribution_date.strftime("%d-%B-%Y"),
            "today_contributions": today_contributions,
            "weekly_contributions": weekly_contributions_list,
        }

        return activity_data

    except HTTPException as e:
        management_error_logger.error(f"Failed to get merry go round activity: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get merry go round activity: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to retrieve merry go round activity"
        )


# updating activities contribution days all of them that the next_contributions_date is behind the current date
@router.put(
    "/update_contribution_days",
    status_code=status.HTTP_200_OK,
)
async def update_activity_contribution_days(
    db: Session = Depends(database.get_db),
):
    try:
        print("==========updating contribution days================")
        # get all activities whose next_contribution_date is behind the current date, from both the activity and activity_contribution_date tables
        today = datetime.now(nairobi_tz).date()

        # fetch activities that need update
        activities = (
            db.query(
                models.ActivityContributionDate.id,
                models.ActivityContributionDate.activity_id,
                models.ActivityContributionDate.frequency,
                models.ActivityContributionDate.next_contribution_date,
                models.ActivityContributionDate.previous_contribution_date,
                models.Activity.interval,
                models.Activity.contribution_day,
            )
            .join(
                models.Activity,
                models.Activity.id == models.ActivityContributionDate.activity_id,
            )
            .filter(
                and_(
                    models.ActivityContributionDate.next_contribution_date < today,
                    models.Activity.last_joining_date <= today,
                )
            )
            .all()
        )

        if not activities:
            return {
                "status": "success",
                "message": "No activity contribution days to update",
            }

        # separate the activities based on their frequency
        (
            daily_updates,
            weekly_updates,
            monthly_updates,
            monthly_custom_updates,
            custom_interval_updates,
        ) = ([], [], [], [], [])

        for activity in activities:
            prev_contribution_date = activity.next_contribution_date
            if activity.frequency == "daily":
                daily_updates.append(
                    {
                        "id": activity.id,
                        "activity_id": activity.activity_id,
                        "next_contribution_date": today,
                        "previous_contribution_date": prev_contribution_date,
                    }
                )
            elif activity.frequency == "weekly":
                next_contribution_date = activity.next_contribution_date + timedelta(
                    days=7
                )
                weekly_updates.append(
                    {
                        "id": activity.id,
                        "activity_id": activity.activity_id,
                        "next_contribution_date": next_contribution_date,
                        "previous_contribution_date": prev_contribution_date,
                    }
                )
            elif activity.frequency == "monthly" and activity.interval == "monthly":
                contribution_day = int(activity.contribution_day)
                year, month = today.year, today.month
                next_contribution_date = get_monthly_next_contribution(
                    year, month, contribution_day
                )
                monthly_updates.append(
                    {
                        "id": activity.id,
                        "activity_id": activity.activity_id,
                        "next_contribution_date": next_contribution_date,
                        "previous_contribution_date": prev_contribution_date,
                    }
                )
            elif activity.frequency == "monthly" and activity.interval in [
                "first",
                "second",
                "third",
                "fourth",
                "last",
            ]:
                contribution_day = activity.contribution_day
                interval = activity.interval
                next_contribution_date = calculate_custom_monthly_date(
                    today, contribution_day, interval
                )
                monthly_custom_updates.append(
                    {
                        "id": activity.id,
                        "activity_id": activity.activity_id,
                        "next_contribution_date": next_contribution_date,
                        "previous_contribution_date": prev_contribution_date,
                    }
                )
            elif activity.frequency == "interval" and activity.interval == "custom":
                next_contribution_date = activity.next_contribution_date + timedelta(
                    days=int(activity.contribution_day)
                )
                custom_interval_updates.append(
                    {
                        "id": activity.id,
                        "activity_id": activity.activity_id,
                        "next_contribution_date": next_contribution_date,
                        "previous_contribution_date": prev_contribution_date,
                    }
                )

        # perform bulk updates in a transaction
        with db.begin_nested():
            for updates in [
                daily_updates,
                weekly_updates,
                monthly_updates,
                monthly_custom_updates,
                custom_interval_updates,
            ]:
                if updates:
                    db.bulk_update_mappings(models.ActivityContributionDate, updates)

        db.commit()
        management_info_logger.info("Activity contribution days updated successfully")
        return {
            "status": "success",
            "message": "Activity contribution days updated successfully",
        }
    except Exception as e:
        db.rollback()
        management_error_logger.error(
            f"Failed to update activity contribution days: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to update activity contribution days"
        )


# funnction to get the last day of a given month and year
def get_last_day_of_month(year, month):
    return monthrange(year, month)[1]


def get_monthly_next_contribution(year, month, contribution_day):
    last_day_of_month = get_last_day_of_month(year, month)
    if contribution_day > last_day_of_month:
        return datetime(year, month, last_day_of_month).date()
    return datetime(year, month, contribution_day).date()


# function to   calculate the next contribution date based on interval and weekday
def get_next_contribution_date(first_day_of_month, weekday_index, interval):
    year = first_day_of_month.year
    month = first_day_of_month.month

    # find the first weekday occurece in the current month
    first_weekday = first_day_of_month + timedelta(
        days=(weekday_index - first_day_of_month.weekday()) % 7
    )

    # calculate the required weekday occurence based on interval
    if interval == "first":
        return first_weekday
    elif interval == "second":
        return first_weekday + timedelta(weeks=1)
    elif interval == "third":
        return first_weekday + timedelta(weeks=2)
    elif interval == "fourth":
        return first_weekday + timedelta(weeks=3)
    elif interval == "last":
        # start from the end of the month and find the last occurence
        last_day_of_month = first_day_of_month.replace(
            day=calendar.monthrange(year, month)[1]
        )
        last_weekday = last_day_of_month - timedelta(
            days=(last_day_of_month.weekday() - weekday_index) % 7
        )
        return last_weekday
    else:
        raise ValueError("Invalid interval value")


def calculate_custom_monthly_date(today, contribution_day, interval):
    weekday_index = list(calendar.day_name).index(contribution_day.capitalize())
    first_day_of_month = today.replace(day=1)
    next_contribution_date = get_next_contribution_date(
        first_day_of_month, weekday_index, interval
    )

    if next_contribution_date < today:
        # move to the first day of the next month
        if first_day_of_month.month == 12:  # handling dec to jan transition
            first_day_of_next_month = first_day_of_month.replace(
                year=first_day_of_month.year + 1, month=1, day=1
            )
        else:
            first_day_of_next_month = first_day_of_month.replace(
                month=first_day_of_month.month + 1, day=1
            )

        # recalculate the contribtion date for the next month
        next_contribution_date = get_next_contribution_date(
            first_day_of_next_month, weekday_index, interval
        )

    return next_contribution_date


# ===calculating missed contributions and setting fines=====
# set fines for missed contributions
@router.post(
    "/set_fines_for_missed_contributions",
    status_code=status.HTTP_201_CREATED,
)
async def set_fines_for_missed_contributions(
    db: Session = Depends(database.get_db),
):
    print("==========setting fines================")
    try:
        # retrieve all activities whose next_contribution_date is behind the current date
        today = datetime.now(nairobi_tz).date()

        # fetch activities that need update
        activities = (
            db.query(
                models.ActivityContributionDate.activity_id,
                models.ActivityContributionDate.chama_id,
                models.ActivityContributionDate.previous_contribution_date,
                models.ActivityContributionDate.next_contribution_date,
                models.Activity.fine,
            )
            .join(
                models.Activity,
                models.Activity.id == models.ActivityContributionDate.activity_id,
            )
            .filter(
                and_(
                    func.date(models.ActivityContributionDate.next_contribution_date)
                    < today,
                    func.date(models.Activity.last_joining_date) < today,
                )
            )
            .all()
        )

        if not activities:
            return {
                "status": "success",
                "message": "No activity contribution days to update",
            }

        activity_ids = [activity.activity_id for activity in activities]

        # retrieve all the users in this activities
        users = (
            db.query(
                models.activity_user_association.c.user_id,
                models.activity_user_association.c.activity_id,
                models.activity_user_association.c.shares,
                models.activity_user_association.c.share_value,
            )
            .filter(models.activity_user_association.c.activity_id.in_(activity_ids))
            .all()
        )

        if not users:
            return {
                "status": "success",
                "message": "No users found for the activities",
            }

        # precompute missed contributions and set fines
        missed_contributions = []

        for activity in activities:
            # filter users by the current activity
            activity_users = [
                user for user in users if user.activity_id == activity.activity_id
            ]

            # calaculate the total contribution for this user in each activity
            for user in activity_users:
                total_contribution = (
                    db.query(
                        func.coalesce(func.sum(models.ActivityTransaction.amount), 0)
                    )
                    .filter(
                        models.ActivityTransaction.activity_id == activity.activity_id,
                        models.ActivityTransaction.user_id == user.user_id,
                        models.ActivityTransaction.transaction_type == "contribution",
                        models.ActivityTransaction.transaction_completed == True,
                        func.date(models.ActivityTransaction.transaction_date)
                        > activity.previous_contribution_date.date(),
                        func.date(models.ActivityTransaction.transaction_date)
                        <= activity.next_contribution_date.date(),
                    )
                    .scalar()
                )

                # calculate missed contribution amount for this user-activity pair
                expected_contribution = user.shares * user.share_value
                missed_amount = expected_contribution - total_contribution

                if missed_amount > 0:
                    fine = activity.fine

                    # check if the user has already been fined for this activity
                    existing_fine = (
                        db.query(models.ActivityFine)
                        .filter(
                            models.ActivityFine.chama_id == activity.chama_id,
                            models.ActivityFine.activity_id == activity.activity_id,
                            models.ActivityFine.user_id == user.user_id,
                            models.ActivityFine.fine_date
                            == activity.next_contribution_date,
                            models.ActivityFine.fine_reason == "missed contribution",
                            models.ActivityFine.is_paid == False,
                            models.ActivityFine.missed_amount == missed_amount,
                            models.ActivityFine.fine == fine,
                        )
                        .first()
                    )

                    if existing_fine:
                        # skip this user-activity pair if they have already been fined
                        continue

                    missed_contributions.append(
                        {
                            "chama_id": activity.chama_id,
                            "activity_id": activity.activity_id,
                            "user_id": user.user_id,
                            "fine": fine,
                            "missed_amount": missed_amount,
                            "expected_repayment": missed_amount + fine,
                            "fine_reason": "missed contribution",
                            "fine_date": activity.next_contribution_date,
                            "is_paid": False,
                        }
                    )

        # perform bulk insert of the fines
        if missed_contributions:
            with db.begin_nested():
                db.bulk_insert_mappings(models.ActivityFine, missed_contributions)

            db.commit()

        return {
            "status": "success",
            "message": "Fines set successfully for missed contributions",
        }
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"Failed to set fines: {e}")
        raise HTTPException(status_code=400, detail="Failed to set fines")


# =============contribution so far================


# get the member recent transactions as well as the manager transaction in the activity
@router.get(
    "/recent_transactions/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_activity_recent_transactions(
    activity_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        # fetch recent transactions by members
        recent_transactions = (
            db.query(
                models.ActivityTransaction.user_id,
                models.ActivityTransaction.amount,
                models.ActivityTransaction.transaction_date,
                models.ActivityTransaction.transaction_type,
                models.User.first_name,
                models.User.last_name,
            )
            .join(models.User, models.User.id == models.ActivityTransaction.user_id)
            .filter(
                models.ActivityTransaction.activity_id == activity_id,
                models.ActivityTransaction.transaction_completed == True,
                models.ActivityTransaction.transaction_type.in_(
                    ["contribution", "late contribution"]
                ),
            )
            .order_by(desc(models.ActivityTransaction.transaction_date))
            .limit(3)
        )

        # TODO: fetch the manager transactions

        recent_transactions_list = [
            {
                "user_name": f"{transaction.first_name} {transaction.last_name}",
                "amount": transaction.amount,
                "transaction_date": transaction.transaction_date.strftime("%d-%B-%Y"),
                "transaction_time": transaction.transaction_date.strftime("%H:%M:%S"),
                "transaction_type": transaction.transaction_type,
            }
            for transaction in recent_transactions
        ]

        return recent_transactions_list
    except HTTPException as e:
        management_error_logger.error(
            f"Failed to get activity recent transactions: {e}"
        )
        raise e
    except Exception as e:
        management_error_logger.error(
            f"Failed to get activity recent transactions: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve activity recent transactions"
        )


# get activities id from name
@router.get(
    "/id/{activity_name}",
    status_code=status.HTTP_200_OK,
)
async def get_activity_id(
    activity_name: str,
    db: Session = Depends(database.get_db),
):

    try:
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.activity_title == activity_name)
            .first()
        )

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        return {"activity_id": activity.id, "activity_type": activity.activity_type}
    except HTTPException as e:
        management_error_logger.error(f"Failed to get activity id: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get activity id: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve activity id")


# get activity members from the activity_user_association table with id
@router.get(
    "/members/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_activity_members(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        # fetch all the members of this activity
        members = (
            db.query(
                models.activity_user_association.c.user_id,
                models.activity_user_association.c.shares,
                models.User.first_name,
                models.User.last_name,
                models.User.phone_number,
                models.User.twitter,
                models.User.facebook,
                models.User.linkedin,
                models.User.profile_picture,
            )
            .join(
                models.User,
                models.User.id == models.activity_user_association.c.user_id,
            )
            .filter(models.activity_user_association.c.activity_id == activity_id)
            .all()
        )

        members_list = [
            {
                "user_id": member.user_id,
                "first_name": member.first_name,
                "last_name": member.last_name,
                "shares": member.shares,
                "phone_number": member.phone_number,
                "twitter": member.twitter,
                "facebook": member.facebook,
                "linkedin": member.linkedin,
                "profile_picture": member.profile_picture,
            }
            for member in members
        ]

        return members_list

    except HTTPException as e:
        management_error_logger.error(f"Failed to get activity members: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get activity members: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to retrieve activity members"
        )


# get about activity
@router.get(
    "/about/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_about_activity(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    # TODO: later retrieve the shares he current user has in this activity and the amount of money he has contributed so far
    # they will have the option to change the number of shares they hold.
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        return {
            "is_manager": True if activity.manager_id == current_user.id else False,
            "profile_picture": current_user.profile_picture,
            "activity_id": activity.id,
            "is_active": "active" if activity.is_active else "inactive",
            "activity_name": activity.activity_title,
            "activity_type": activity.activity_type,
            "activity_description": activity.activity_description,
            "activity_amount": f"Ksh {activity.activity_amount}",
            "activity_frequency": activity.frequency,
            "activity_interval": activity.interval,
            "activity_contribution_day": activity.contribution_day,
            "accepting_new_members": (
                "Accepting Members"
                if activity.accepting_members
                else "Not Accepting Members"
            ),
            "activity_creation_date": activity.creation_date.strftime("%d-%B-%Y"),
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to get activity about: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get activity about: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve activity about")


# toggle the status of accepting members in an activity
@router.put(
    "/accepting_members/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def toggle_accepting_members(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        # toggle the accepting_members status
        activity.accepting_members = not activity.accepting_members
        db.commit()

        return {
            "status": "success",
            "message": "Accepting members status updated successfully",
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to toggle accepting members: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to toggle accepting members: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to toggle accepting members"
        )


# toggle the is_active status of the activity
@router.put(
    "/is_active/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def toggle_is_active(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        # toggle the is_active status
        activity.is_active = not activity.is_active
        db.commit()

        return {
            "status": "success",
            "message": "Activity status updated successfully",
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to toggle activity status: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to toggle activity status: {e}")
        raise HTTPException(status_code=400, detail="Failed to toggle activity status")


# toggle restart status of the activity and enter restart_date
@router.put(
    "/restart/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def toggle_restart_activity(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        # toggle the restart status
        activity.restart = not activity.restart
        activity.restart_date = datetime.now(nairobi_tz).replace(
            tzinfo=None, microsecond=0
        )
        db.commit()

        return {
            "status": "success",
            "message": "Activity restart status updated successfully",
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to toggle activity restart status: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to toggle activity restart status: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to toggle activity restart status"
        )


# toggle is_deleted status of the activity
@router.put(
    "/is_deleted/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def toggle_is_deleted_activity(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        # toggle the is_deleted status
        activity.is_deleted = not activity.is_deleted
        db.commit()

        return {
            "status": "success",
            "message": "Activity deletion status updated successfully",
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to toggle activity deletion status: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to toggle activity deletion status: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to toggle activity deletion status"
        )
