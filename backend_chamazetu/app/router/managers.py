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

router = APIRouter(prefix="/managers", tags=["managers"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")

share_names = [
    "Alpha",
    "Beta",
    "Gamma",
    "Delta",
    "Epsilon",
    "Zeta",
    "Eta",
    "Theta",
    "Iota",
    "Kappa",
    "Lambda",
    "Mu",
    "Nu",
    "Xi",
    "Omicron",
    "Pi",
    "Rho",
    "Sigma",
    "Tau",
    "Upsilon",
    "Phi",
    "Chi",
    "Psi",
    "Omega",
]


# the dashboard for a manager
@router.get(
    "/dashboard",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ManagerDashboardResp,
)
async def get_manager_dashboard(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        manager = (
            db.query(models.User).filter(models.User.id == current_user.id).first()
        )
        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

        # get all chamas connected to manager id
        chama_data = (
            db.query(
                models.Chama.id,
                models.Chama.chama_name,
                models.Chama.is_active,
                func.count(models.chama_user_association.c.user_id).label(
                    "member_count"
                ),
            )
            .join(
                models.chama_user_association,
                models.chama_user_association.c.chama_id == models.Chama.id,
                isouter=True,
            )
            .filter(models.Chama.manager_id == current_user.id)
            .group_by(models.Chama.id)
            .all()
        )

        chamas = [
            {
                "chama_id": chama.id,
                "chama_name": chama.chama_name,
                "member_count": chama.member_count,
                "is_active": chama.is_active,
            }
            for chama in chama_data
        ]

        # get updates and features
        updates_and_features = (
            db.query(
                models.Manager_Update_Feature.feature_title,
                models.Manager_Update_Feature.description,
                models.Manager_Update_Feature.feature_date,
            )
            .order_by(models.Manager_Update_Feature.feature_date.desc())
            .limit(5)
            .all()
        )

        updates_and_features_list = [
            {
                "feature_title": feature.feature_title,
                "feature_description": feature.feature_description,
                "feature_date": feature.feature_date,
            }
            for feature in updates_and_features
        ]

        manager_dashboard = {
            "manager_id": current_user.id,
            "user_email": current_user.email,
            "manager_profile_picture": manager.profile_picture,
            "chamas": chamas,
            "updates_and_features": updates_and_features_list,
        }

        return manager_dashboard
    except Exception as e:
        management_error_logger.error(f"failed to get manager dashboard, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to get manager dashboard")


# manager allowing a late joining for the chama
@router.post("/allow_new_chama_members/{chama_id}", status_code=status.HTTP_201_CREATED)
async def allow_new_chama_members(
    chama_id: int,
    activation_data: schemas.newChamaMembers = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        today = datetime.now(nairobi_tz).date()
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        if chama.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not allowed to allow new chama members"
            )

        #  check for an existing active record
        deadline = datetime.strptime(activation_data.deadline, "%Y-%m-%d").date()

        active_record = (
            db.query(models.ChamaLateJoining)
            .filter(
                and_(
                    models.ChamaLateJoining.chama_id == chama_id,
                    func.date(models.ChamaLateJoining.deadline) >= today,
                )
            )
            .first()
        )

        if active_record:
            raise HTTPException(
                status_code=400, detail="An active late joining record already exists"
            )

        # create a new late joining record
        new_record = models.ChamaLateJoining(
            chama_id=chama_id,
            deadline=deadline,
            late_joining_fee=activation_data.late_joining_fee,
        )

        db.add(new_record)
        db.commit()

        return {"message": "New chama members allowed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"failed to allow new chama members, error: {http_exc}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"failed to allow new chama members, error: {exc}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to allow new chama members"
        )


# get all chamas connected to manager id
@router.get(
    "/chamas",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.ManagerChamasResp],
)
async def get_manager_chamas(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    try:
        manager_chamas = (
            db.query(models.Chama)
            .filter(models.Chama.manager_id == current_user.id)
            .all()
        )

        return [schemas.ManagerChamasResp.from_orm(chama) for chama in manager_chamas]

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to get manager chamas")


# access chama by ID for a logged in manager
@router.get(
    "/chama/{group_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ChamaDashboardResp,
)
async def get_chama(
    group_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == group_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        activities = (
            db.query(models.ActivityContributionDate)
            .filter(
                and_(
                    models.ActivityContributionDate.chama_id == group_id,
                    models.ActivityContributionDate.activity_is_active == True,
                )
            )
            .order_by(desc(models.ActivityContributionDate.next_contribution_date))
            .all()
        )

        activities_ids = [activity.activity_id for activity in activities]

        # total unpaid fines
        total_fines = (
            db.query(func.coalesce(func.sum(models.ActivityFine.expected_repayment), 0))
            .filter(
                and_(
                    models.ActivityFine.chama_id == group_id,
                    models.ActivityFine.is_paid == False,
                    models.ActivityFine.activity_id.in_(activities_ids),
                )
            )
            .scalar()
        )

        # retrieving chama investment balance
        invst_account = (
            db.query(models.Investment_Performance)
            .filter(models.Investment_Performance.chama_id == group_id)
            .first()
        )

        # retrieving chama account balance
        acct_balance = (
            db.query(models.Chama_Account)
            .filter(models.Chama_Account.chama_id == group_id)
            .first()
        )

        manager_profile = (
            db.query(models.User.profile_picture)
            .filter(models.User.id == current_user.id)
            .scalar()
        )

        # TODO: retrieve mmf activity withdrawal/ deposit history limit 3

        # organizing response data
        investment_balance = invst_account.amount_invested if invst_account else 0.0
        general_account = acct_balance.account_balance if acct_balance else 0.0
        available_balance = acct_balance.available_balance if acct_balance else 0.0

        chama_activities = [
            {
                "contribution_date": activity.next_contribution_date,
                "title": activity.activity_title,
                "type": activity.activity_type,
                "activity_id": activity.activity_id,
            }
            for activity in activities
        ]

        # return response
        return {
            "chama": {
                "manager_id": current_user.id,
                "manager_profile_picture": manager_profile,
                "investment_balance": investment_balance,
                "general_account": general_account,
                "available_balance": available_balance,
                "total_fines": total_fines,
                "activities": chama_activities,
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        management_error_logger.error(f"failed to get chama by id, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by id")


# retrieve the lates 5 updates and features of a chama APP
@router.get(
    "/updates_and_features",
    status_code=status.HTTP_200_OK,
)
async def get_updates_and_features(
    db: Session = Depends(database.get_db),
):
    updates_and_features = (
        db.query(models.Manager_Update_Feature)
        .order_by(models.Manager_Update_Feature.feature_date.desc())
        .limit(5)
        .all()
    )

    if not updates_and_features:
        raise HTTPException(
            status_code=404, detail="No updates and features found for managers"
        )
    return updates_and_features


# get manager profile image
@router.get(
    "/profile_picture",
    status_code=status.HTTP_200_OK,
)
async def get_manager_profile_image(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    try:
        manager = (
            db.query(models.User).filter(models.User.id == current_user.id).first()
        )

        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

        return manager.profile_picture

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get manager profile image"
        )


@router.get(
    "/profile_picture/{manager_id}",
    status_code=status.HTTP_200_OK,
)
async def get_manager_profile_picture(
    manager_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        manager = db.query(models.User).filter(models.User.id == manager_id).first()

        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

        return manager.profile_picture

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get manager profile image"
        )


"""
id | activity_title | activity_amount | frequency | interval | contribution_day | first_contribution_date 
----+----------------+-----------------+-----------+----------+------------------+-------------------------
  1 | activity one   |             300 | daily     | daily    | daily            | 2024-08-26 00:00:00
  2 | activity two   |             340 | weekly    | weekly   | tuesday          | 2024-08-27 00:00:00
  3 | activity three |             450 | monthly   | third    | tuesday          | 2024-08-27 00:00:00
  4 | activity four  |             340 | interval  | custom   | 12               | 2024-08-29 00:00:00
  6 | daily savings  |             100 | daily     | daily    | daily            | 2024-09-13 00:00:00
  7 | daily merry    |             100 | daily     | daily    | daily            | 2024-09-13 00:00:00
  5 | chama family   |             200 | monthly   | monthly  | 23               | 2024-09-07 00:00:00
"""


@router.post(
    "/random_rotation_order/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def create_random_rotation_order(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        if activity.activity_type != "merry-go-round":
            raise HTTPException(
                status_code=400, detail="Activity is not a merry-go-round"
            )
        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not allowed to create rotation order"
            )

        cycle_number = chama_activity.current_activity_cycle()
        if cycle_number == 0:
            cycle_number = 1
        else:
            cycle_number += 1

        print("=============cycle number", cycle_number)

        share_value = activity.activity_amount
        frequency = activity.frequency
        interval = activity.interval
        contribution_day = activity.contribution_day
        first_contribution_date = activity.first_contribution_date

        next_contribution_date = chama_activity.previous_and_upcoming_contribution_dates()["next_contribution_date"]
        print("======next contribution date", next_contribution_date)

        # get all users in the chama from the activity_user_association table, we will need the user_id, user_name, share_value, number of shares
        # user name is from the user table as firstname and lastname

        users = (
            db.query(
                models.User.id,
                models.User.first_name,
                models.User.last_name,
                models.activity_user_association.c.share_value,
                models.activity_user_association.c.shares,
            )
            .join(
                models.activity_user_association,
                models.activity_user_association.c.user_id == models.User.id,
            )
            .filter(
                and_(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.activity_is_active == True,
                    models.activity_user_association.c.user_is_active == True,
                )
            )
            .all()
        )

        print("======users", users)

        if not users:
            raise HTTPException(
                status_code=404, detail="No users found in the activity"
            )

        number_of_activity_users = len(users)
        number_of_shares = sum([user.shares for user in users])
        expected_receiving_amount = number_of_shares * share_value

        # create a rotation order for each user in the activity
        rotation_order = []

        print("======expected receiving amount", expected_receiving_amount)
        for user in users:
            for i in range(user.shares):
                rotation_order.append(
                    {
                        "recipient_id": user.id,
                        "user_name": f"{user.first_name} {user.last_name}",
                        "share_value": user.share_value,
                        "share_name": share_names[i],
                        "activity_id": activity.id,
                        "expected_amount": expected_receiving_amount,
                    }
                )

        # shuffle the rotation order
        shuffled_order = utils.shuffle_list(rotation_order)
        print("=====past the shuffling=================")

        # we will now include the receiving date for each user in the rotation order as well as their order_in_rotation number(1, 2 ...),
        # the dates will follow the frequency and interval of the activity
        # TODO Improve this by allowing the manager to set the first contribution date for the next cycle - create a new route to handle cycleNum > 1
        set_contribution_date = None
        if cycle_number == 1:
            set_contribution_date = first_contribution_date
        else:
            set_contribution_date = next_contribution_date

        for i, order in enumerate(shuffled_order):
            shuffled_order[i]["receiving_date"] = set_contribution_date
            shuffled_order[i]["order_in_rotation"] = i + 1
            shuffled_order[i]["cycle_number"] = cycle_number
            shuffled_order[i]["chama_id"] = activity.chama_id
            shuffled_order[i]["received_amount"] = 0

            if frequency == "daily":
                receiving_date = calculate_daily_interval(set_contribution_date)
            elif frequency == "weekly":
                receiving_date = calculate_weekly_interval(set_contribution_date)
            elif frequency == "monthly" and interval in [
                "first",
                "second",
                "third",
                "fourth",
                "last",
            ]:
                receiving_date = calculate_monthly_interval(
                    set_contribution_date, interval, contribution_day
                )
            elif frequency == "monthly" and interval == "monthly":
                receiving_date = calculate_monthly_same_day_interval(
                    set_contribution_date, int(contribution_day)
                )
            elif frequency == "interval" and interval == "custom":
                receiving_date = calculate_custom_interval(
                    set_contribution_date, int(contribution_day)
                )

            # update the set_contribution_date for the next user
            set_contribution_date = receiving_date

        print("======final rotation order======")
        # print(shuffled_order)

        # insert the rotation order into the database
        db.bulk_insert_mappings(models.RotationOrder, shuffled_order)

        db.commit()
        return {"message": "Rotation order created successfully"}
    except HTTPException as e:
        db.rollback()
        management_error_logger.error(
            f"failed to create rotation order for chama, error: {e}"
        )
        print("http exception", e)
        raise e
    except Exception as e:
        db.rollback()
        management_error_logger.error(
            f"failed to create rotation order for chama, error: {e}"
        )
        print("exception", e)
        raise HTTPException(
            status_code=400, detail="Failed to create rotation order for chama"
        )


# disburse funds to the user in the rotation order
# since it can only be disbursed after one rotation is done, we will disburse to the user in the previous date, we will check
# the previous date has to be behind today and next contribution upcoming
# NOTE: this route only works if the rotation_date is the same as the next_contribution_date == today - testing on daily activities
@router.post(
    "/disburse_funds/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def disburse_funds(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = await get_active_activity_by_id(activity_id, db)
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        if activity.activity_type != "merry-go-round":
            raise HTTPException(
                status_code=400, detail="Activity is not a merry-go-round"
            )
        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not allowed to disburse funds"
            )

        contribution_dates = (
            db.query(models.ActivityContributionDate)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .first()
        )

        previous_contribution_date = (
            contribution_dates.previous_contribution_date.date()
        )
        next_contribution_date = contribution_dates.next_contribution_date.date()
        today = datetime.now(nairobi_tz).date()

        pooled_amount = (
            db.query(
                func.coalesce(
                    func.sum(models.RotatingContributions.contributed_amount), 0
                )
            )
            .filter(
                and_(
                    models.RotatingContributions.activity_id == activity_id,
                    models.RotatingContributions.rotation_date
                    == previous_contribution_date,
                )
            )
            .scalar()
        )

        if not pooled_amount:
            raise HTTPException(
                status_code=404, detail="No pooled amount found for disbursement"
            )

        if today <= previous_contribution_date or today == next_contribution_date:
            raise HTTPException(
                status_code=400,
                detail="Cannot disburse funds before the previous contribution date",
            )

        # get the cycle number for the activity
        cycle_number = (
            db.query(func.coalesce(func.max(models.RotationOrder.cycle_number), 0))
            .filter(models.RotationOrder.activity_id == activity_id)
            .scalar()
        )

        if cycle_number == 0:
            raise HTTPException(
                status_code=400, detail="No rotation order has been created yet"
            )

        recipient = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.receiving_date == previous_contribution_date,
                    models.RotationOrder.cycle_number == cycle_number,
                    models.RotationOrder.received_amount == 0,
                    models.RotationOrder.fulfilled == False,
                )
            )
            .first()
        )

        if not recipient:
            raise HTTPException(
                status_code=404, detail="No recipient found for disbursement"
            )

        # begin transaction block
        with db.begin_nested():
            # update the recipient's received amount and their wallet balance
            recipient_record = (
                db.query(models.User)
                .filter(
                    models.User.id == recipient.recipient_id,
                )
                .with_for_update()
                .first()
            )

            if not recipient_record:
                raise HTTPException(status_code=404, detail="Recipient not found")
            recipient_record.wallet_balance += pooled_amount

            # update the rotation order record
            recipient.received_amount = pooled_amount
            recipient.fulfilled = recipient.expected_amount == recipient.received_amount

            # update chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == recipient.chama_id)
                .with_for_update()
                .first()
            )

            if not chama_account:
                raise HTTPException(status_code=404, detail="Chama account not found")
            chama_account.account_balance -= pooled_amount

            # update activity account balance
            activity_account = (
                db.query(models.Activity_Account)
                .filter(models.Activity_Account.activity_id == recipient.activity_id)
                .with_for_update()
                .first()
            )

            if not activity_account:
                raise HTTPException(
                    status_code=404, detail="Activity account not found"
                )

            activity_account.account_balance -= pooled_amount

        db.commit()
        return {"message": "Funds disbursed successfully"}
    except HTTPException as e:
        db.rollback()
        management_error_logger.error(f"failed to disburse funds, error: {e}")
        raise e
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"failed to disburse funds, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to disburse funds")


# automating the above route
# this route will be called by a cron job to disburse funds to the recipient
# this routes runs after there has been an update in he contribuion dates hence we can use the
# previous date to get the recipient whose contribution time has has just completed and disburse funds to them
# this will handle those members who have set to receive their disbursements onto their wallets and not mpesa
##TODO: another route to disburse to mpesa directly - might have to use callbacks


# difference will be, this route will disburse for all activities that meet the criteria of the previous date
# this route will be called after the contribution date has passed
# this route will be called by a cron job
@router.post(
    "/auto_disbursement",
    status_code=status.HTTP_201_CREATED,
)
async def auto_disbursement(
    db: Session = Depends(database.get_db),
):
    try:
        today = datetime.now(nairobi_tz).date()
        # get all activities that have passed their contribution date
        # might add a filter for if in the rotatioOrder table, the fulfilled is false for the previous date
        activities = (
            db.query(models.Activity)
            .join(
                models.ActivityContributionDate,
                models.ActivityContributionDate.activity_id == models.Activity.id,
            )
            .filter(
                and_(
                    func.date(
                        models.ActivityContributionDate.previous_contribution_date
                    )
                    < today,
                    func.date(models.ActivityContributionDate.next_contribution_date)
                    > today,
                )
            )
            .all()
        )

        if not activities:
            return {"message": "No activities found for disbursement"}

        for activity in activities:
            contribution_dates = (
                db.query(models.ActivityContributionDate)
                .filter(
                    models.ActivityContributionDate.activity_id == activity.id,
                )
                .first()
            )

            previous_contribution_date = (
                contribution_dates.previous_contribution_date.date()
            )
            next_contribution_date = contribution_dates.next_contribution_date.date()

            if today <= previous_contribution_date or today == next_contribution_date:
                continue

            # get the poooled amount for the activity for the previous contribution date
            pooled_amount = (
                db.query(
                    func.coalesce(
                        func.sum(models.RotatingContributions.contributed_amount), 0
                    )
                )
                .filter(
                    and_(
                        models.RotatingContributions.activity_id == activity.id,
                        models.RotatingContributions.rotation_date
                        == previous_contribution_date,
                    )
                )
                .scalar()
            )

            if not pooled_amount:
                continue

            if today <= previous_contribution_date:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot disburse funds before the rotation date passes",
                )

            # get the current cycle number for the activity
            cycle_number = (
                db.query(func.coalesce(func.max(models.RotationOrder.cycle_number), 0))
                .filter(models.RotationOrder.activity_id == activity.id)
                .scalar()
            )

            if cycle_number == 0:
                continue

            # find the recipient in the rotation order who is to receive the funds
            recipient = (
                db.query(models.RotationOrder)
                .filter(
                    and_(
                        models.RotationOrder.activity_id == activity.id,
                        models.RotationOrder.receiving_date
                        == previous_contribution_date,
                        models.RotationOrder.cycle_number == cycle_number,
                        models.RotationOrder.received_amount == 0,
                        models.RotationOrder.fulfilled == False,
                    )
                )
                .first()
            )

            if not recipient:
                continue

            # begin transaction block for atomicity
            with db.begin_nested():
                # update the recipient's received amount and their wallet balance
                recipient_record = (
                    db.query(models.User)
                    .filter(models.User.id == recipient.recipient_id)
                    .with_for_update()
                    .first()
                )

                if not recipient_record:
                    raise HTTPException(status_code=404, detail="Recipient not found")

                recipient_record.wallet_balance += pooled_amount

                # update the rotation order record
                recipient.received_amount = pooled_amount
                recipient.fulfilled = (
                    recipient.expected_amount == recipient.received_amount
                )

                # update chama account balance
                chama_account = (
                    db.query(models.Chama_Account)
                    .filter(models.Chama_Account.chama_id == recipient.chama_id)
                    .with_for_update()
                    .first()
                )

                if not chama_account:
                    raise HTTPException(
                        status_code=404, detail="Chama account not found"
                    )
                chama_account.account_balance -= pooled_amount

                # update activity account balance
                activity_account = (
                    db.query(models.Activity_Account)
                    .filter(
                        models.Activity_Account.activity_id == recipient.activity_id
                    )
                    .with_for_update()
                    .first()
                )

                if not activity_account:
                    raise HTTPException(
                        status_code=404, detail="Activity account not found"
                    )

                activity_account.account_balance -= pooled_amount

            db.commit()
        return {"message": "Funds disbursed successfully"}
    except HTTPException as e:
        db.rollback()
        management_error_logger.error(f"failed to disburse funds, error: {e}")
        raise e
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"failed to disburse funds, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to disburse funds")


# auto disbursement for merry-go-round activities
@router.post(
    "/auto_disburse_to_wallets",
    status_code=status.HTTP_201_CREATED,
)
async def auto_disburse_to_wallets(
    db: Session = Depends(database.get_db),
):
    try:
        today = datetime.now(nairobi_tz).date()
        # recipients for previous date
        recipients = (
            db.query(models.RotationOrder)
            .join(
                models.ActivityContributionDate,
                models.ActivityContributionDate.activity_id
                == models.RotationOrder.activity_id,
            )
            .filter(
                and_(
                    models.RotationOrder.receiving_date
                    == models.ActivityContributionDate.previous_contribution_date,
                    models.RotationOrder.fulfilled == False,
                    models.RotationOrder.received_amount == 0,
                    models.ActivityContributionDate.activity_is_active == True,
                )
            )
            .all()
        )

        if not recipients:
            return {"message": "No recipients found for disbursement"}

        for recipient in recipients:
            activity_id = recipient.activity_id
            chama_id = recipient.chama_id
            user_id = recipient.recipient_id


            # get the pooled amount for the recipient
            pooled_so_far = (
                db.query(
                    func.coalesce(
                        func.sum(models.RotatingContributions.contributed_amount), 0
                    )
                )
                .filter(
                    and_(
                        models.RotatingContributions.activity_id == activity_id,
                        models.RotatingContributions.rotation_date
                        == recipient.receiving_date,
                        models.RotatingContributions.recipient_id == user_id,
                    )
                )
                .scalar()
            )

            if not pooled_so_far:
                continue

            # begin transaction block for atomicity
            with db.begin_nested():
                # update the recipient's received amount and their wallet balance
                recipient_record = (
                    db.query(models.User)
                    .filter(models.User.id == user_id)
                    .with_for_update()
                    .first()
                )

                if not recipient_record:
                    raise HTTPException(status_code=404, detail="Recipient not found")


                recipient_record.wallet_balance += pooled_so_far

                # update the rotation order record
                recipient.received_amount = pooled_so_far
                recipient.fulfilled = (
                    recipient.expected_amount == recipient.received_amount
                )

                # update chama account balance
                chama_account = (
                    db.query(models.Chama_Account)
                    .filter(models.Chama_Account.chama_id == chama_id)
                    .with_for_update()
                    .first()
                )

                if not chama_account:
                    raise HTTPException(
                        status_code=404, detail="Chama account not found"
                    )
                chama_account.account_balance -= pooled_so_far

                # update activity account balance
                activity_account = (
                    db.query(models.Activity_Account)
                    .filter(models.Activity_Account.activity_id == activity_id)
                    .with_for_update()
                    .first()
                )

                if not activity_account:
                    raise HTTPException(
                        status_code=404, detail="Activity account not found"
                    )

                activity_account.account_balance -= pooled_so_far

            db.commit()
        return {"message": "Funds disbursed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(f"failed to disburse funds, error: {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"failed to disburse funds, error: {exc}")
        raise HTTPException(status_code=400, detail="Failed to disburse funds")


"""
# this to disburse late contributions from the the late_rotation_disbursement table
@router.post(
    "/disburse_late_contributions",
    status_code=status.HTTP_201_CREATED,
)
async def disburse_late_contributions(
    db: Session = Depends(database.get_db),
):
    try:
        today = datetime.now(nairobi_tz).date()
        # recipients for previous date
        late_disbursements = (
            db.query(models.LateRotationDisbursements)
            .filter(models.LateRotationDisbursements.disbursement_completed == False)
            .all()
        )
        print("late", len(late_disbursements))

        if not late_disbursements:
            return {"message": "No recipients found for disbursement"}

        # collecting late recipient ids, missed rotation dates and activity ids
        late_recipient_ids = [
            disbursement.late_recipient_id for disbursement in late_disbursements
        ]
        missed_rotation_dates = [
            disbursement.missed_rotation_date for disbursement in late_disbursements
        ]
        activity_ids = [disbursement.activity_id for disbursement in late_disbursements]

        # from rotation order, retrieve matching records for the late disbursements
        unfulfilled_rotation_orders = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.recipient_id.in_(late_recipient_ids),
                    models.RotationOrder.receiving_date.in_(missed_rotation_dates),
                    models.RotationOrder.activity_id.in_(activity_ids),
                    models.RotationOrder.fulfilled == False,
                )
            )
            .all()
        )

        if not unfulfilled_rotation_orders:
            return {"message": "No unfulfilled rotation orders found for disbursement"}

        # group disbursements by user, activity and chama
        disbursements_by_user = {}
        for disbursement in late_disbursements:
            user_id = disbursement.late_recipient_id
            chama_id = disbursement.chama_id
            activity_id = disbursement.activity_id

            # retrieve the rotation order record for this disbursement
            rotation_order = next(
                (
                    order
                    for order in unfulfilled_rotation_orders
                    if order.recipient_id == user_id
                    and order.receiving_date == disbursement.missed_rotation_date
                    and order.activity_id == activity_id
                ),
                None,
            )

            if not rotation_order:
                # there should be a rotation order for each disbursement
                print("====rotation order not found====")
                management_error_logger.error(
                    f"rotation order not found for disbursement, user_id: {user_id}, activity_id: {activity_id}, rotation_date: {disbursement.missed_rotation_date}"
                )
                continue

            # group disbursements by user
            if user_id not in disbursements_by_user:
                disbursements_by_user[user_id] = {
                    "total_disbursement": 0,
                    "activity_chama_updates": {},
                }

            # increment the total disbursement for the user
            disbursements_by_user[user_id][
                "total_disbursement"
            ] += disbursement.late_contribution

            # store disbursement details for activity and chama updates
            key = (activity_id, chama_id)
            if key not in disbursements_by_user[user_id]["activity_chama_updates"]:
                disbursements_by_user[user_id]["activity_chama_updates"][key] = 0
            disbursements_by_user[user_id]["activity_chama_updates"][
                key
            ] += disbursement.late_contribution

        # process each user's disbursements
        for user_id, disbursement_data in disbursements_by_user.items():
            total_disbursement = disbursement_data["total_disbursement"]

            # begin transaction block for atomicity
            try:
                with db.begin_nested():
                    # deduct from the respective activity and chama accounts
                    for (activity_id, chama_id), amount in disbursement_data[
                        "activity_chama_updates"
                    ].items():
                        # update activity account balance
                        activity_account = (
                            db.query(models.Activity_Account)
                            .filter(models.Activity_Account.activity_id == activity_id)
                            .with_for_update()
                            .first()
                        )

                        # update chama account balance
                        chama_account = (
                            db.query(models.Chama_Account)
                            .filter(models.Chama_Account.chama_id == chama_id)
                            .with_for_update()
                            .first()
                        )

                        if not activity_account or not chama_account:
                            raise HTTPException(
                                status_code=404, detail="Account not found"
                            )

                        if (
                            chama_account.account_balance < total_disbursement
                            or activity_account.account_balance < total_disbursement
                        ):
                            raise HTTPException(
                                status_code=400,
                                detail="Insufficient funds in chama account",
                            )

                        activity_account.account_balance -= amount
                        chama_account.account_balance -= amount

                    # update the recipients wallet balance
                    user_wallet = (
                        db.query(models.User)
                        .filter(models.User.id == user_id)
                        .with_for_update()
                        .first()
                    )
                    if not user_wallet:
                        raise HTTPException(
                            status_code=404, detail="Recipient not found"
                        )

                    user_wallet.wallet_balance += total_disbursement

                    # mark the disbursements as completed
                    db.query(models.LateRotationDisbursements).filter(
                        models.LateRotationDisbursements.late_recipient_id == user_id,
                        models.LateRotationDisbursements.disbursement_completed
                        == False,
                    ).update(
                        {"disbursement_completed": True},
                        synchronize_session=False,
                    )

                    # update the rotation order as fulfilled if necessary
                    for disbursement in late_disbursements:
                        rotation_order = next(
                            (
                                order
                                for order in unfulfilled_rotation_orders
                                if order.recipient_id == disbursement.late_recipient_id
                                and order_receiving_date
                                == disbursement.missed_rotation_date
                                and order.activity_id == disbursement.activity_id
                            ),
                            None,
                        )
                        if rotation_order:
                            rotation_order.received_amount += (
                                disbursement.late_contribution
                            )
                            if (
                                rotation_order.received_amount
                                >= rotation_order.expected_amount
                            ):
                                rotation_order.fulfilled = True

                db.commit()  # commit the transaction for this user
            except Exception as e:
                db.rollback()
                management_error_logger.error(f"failed to disburse funds, error: {e}")
                # skip to the next user
                continue

        return {"message": "Funds disbursed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(f"failed to disburse funds, error: {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"failed to disburse funds, error: {exc}")
        raise HTTPException(status_code=400, detail="Failed to disburse funds")
"""


# rewriting the above route in a more simplified way
@router.post(
    "/backup_auto_disburse_late_contributions",
    status_code=status.HTTP_201_CREATED,
)
async def auto_disburse_late_contributions(
    db: Session = Depends(database.get_db),
):

    try:
        today = datetime.now(nairobi_tz).date()
        # recipients for previous date
        late_disbursements = (
            db.query(models.LateRotationDisbursements)
            .filter(models.LateRotationDisbursements.disbursement_completed == False)
            .all()
        )

        if not late_disbursements:
            print("====no recipients found for disbursement====")
            return {"message": "No recipients found for disbursement"}

        # collecting late recipient ids, missed rotation dates and activity ids
        late_recipient_ids = [
            disbursement.late_recipient_id for disbursement in late_disbursements
        ]
        missed_rotation_dates = [
            disbursement.missed_rotation_date for disbursement in late_disbursements
        ]
        activity_ids = [disbursement.activity_id for disbursement in late_disbursements]

        # from rotation order, retrieve matching records for the late disbursements
        unfulfilled_rotation_orders = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.recipient_id.in_(late_recipient_ids),
                    models.RotationOrder.receiving_date.in_(missed_rotation_dates),
                    models.RotationOrder.activity_id.in_(activity_ids),
                    models.RotationOrder.fulfilled == False,
                )
            )
            .all()
        )

        if not unfulfilled_rotation_orders:
            print("====no unfulfilled rotation orders found for disbursement====")
            return {"message": "No unfulfilled rotation orders found for disbursement"}

        # group disbursements and rotation ordes by user_id
        user_disbursements_map = defaultdict(list)
        user_rotation_orders_map = defaultdict(list)

        for disbursement in late_disbursements:
            user_disbursements_map[disbursement.late_recipient_id].append(disbursement)

        for order in unfulfilled_rotation_orders:
            user_rotation_orders_map[order.recipient_id].append(order)

        unique_user_ids = list(user_disbursements_map.keys())

        for user_id in unique_user_ids:
            print("====user======", user_id)
            user_disbursements = user_disbursements_map.get(user_id, [])
            user_rotation_orders = user_rotation_orders_map.get(user_id, [])

            if not user_disbursements or not user_rotation_orders:
                print("====no disbursements or rotation orders found====")
                continue

            total_to_disburse = 0
            # begin transaction block for atomicity
            try:
                with db.begin_nested():
                    # process each disbursement for the user
                    for disbursement in user_disbursements:
                        activity_id = disbursement.activity_id
                        chama_id = disbursement.chama_id
                        amount = disbursement.late_contribution

                        # retrieve the rotation order record for this disbursement
                        rotation_order = next(
                            (
                                order
                                for order in user_rotation_orders
                                if order.receiving_date
                                == disbursement.missed_rotation_date
                                and order.activity_id == activity_id
                            ),
                            None,
                        )

                        if not rotation_order:
                            # there should be a rotation order for each disbursement
                            print("====rotation order not found====")
                            management_error_logger.error(
                                f"rotation order not found for disbursement, user_id: {user_id}, activity_id: {disbursement.activity_id}, rotation_date: {disbursement.missed_rotation_date}"
                            )
                            continue

                        # update activity account balance
                        activity_account = (
                            db.query(models.Activity_Account)
                            .filter(models.Activity_Account.activity_id == activity_id)
                            .with_for_update()
                            .first()
                        )

                        # update chama account balance
                        chama_account = (
                            db.query(models.Chama_Account)
                            .filter(models.Chama_Account.chama_id == chama_id)
                            .with_for_update()
                            .first()
                        )

                        if not activity_account or not chama_account:
                            raise HTTPException(
                                status_code=404, detail="Account not found"
                            )

                        if (
                            chama_account.account_balance < amount
                            or activity_account.account_balance < amount
                        ):
                            raise HTTPException(
                                status_code=400,
                                detail="Insufficient funds in chama account",
                            )

                        activity_account.account_balance -= amount
                        chama_account.account_balance -= amount

                        total_to_disburse += amount

                        # update the rotation order as fulfilled if necessary
                        rotation_order.received_amount += amount
                        rotation_order.fulfilled = (
                            rotation_order.received_amount
                            >= rotation_order.expected_amount
                        )

                    # mark the disbursements as completed
                    db.query(models.LateRotationDisbursements).filter(
                        models.LateRotationDisbursements.late_recipient_id == user_id,
                        models.LateRotationDisbursements.disbursement_completed
                        == False,
                    ).update(
                        {"disbursement_completed": True},
                        synchronize_session=False,
                    )

                    # update the user's wallet balance
                    user_wallet = (
                        db.query(models.User)
                        .filter(models.User.id == user_id)
                        .with_for_update()
                        .first()
                    )

                    if not user_wallet:
                        raise HTTPException(
                            status_code=404, detail="Recipient not found"
                        )

                    user_wallet.wallet_balance += total_to_disburse

                # commit the transaction for this user
                print("====committing transaction====")
                db.commit()
            except Exception as e:
                print("====rolling back transaction====")
                db.rollback()
                management_error_logger.error(f"failed to disburse funds, error: {e}")
                # skip to the next user
                continue

        return {"message": "Funds disbursed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(f"failed to disburse funds, error: {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"failed to disburse funds, error: {exc}")
        raise HTTPException(status_code=400, detail="Failed to disburse funds")


@router.post(
    "/auto_disburse_late_contributions",
    status_code=status.HTTP_201_CREATED,
)
async def auto_disburse_late_contributions(
    db: Session = Depends(database.get_db),
):
    try:
        today = datetime.now(nairobi_tz).date()

        # Join LateRotationDisbursements with RotationOrder to retrieve matching records
        late_disbursements = (
            db.query(models.LateRotationDisbursements, models.RotationOrder)
            .join(
                models.RotationOrder,
                and_(
                    models.LateRotationDisbursements.late_recipient_id
                    == models.RotationOrder.recipient_id,
                    models.LateRotationDisbursements.missed_rotation_date
                    == models.RotationOrder.receiving_date,
                    models.LateRotationDisbursements.activity_id
                    == models.RotationOrder.activity_id,
                ),
            )
            .filter(models.LateRotationDisbursements.disbursement_completed == False)
            .all()
        )
        """
        the above route might need to add filterr of is_fulfilled = False
        expected_amount != contributed_amount
        remember late disbursement include fines which are not part of the expected amount
        #TODO: this is an assumption but wait till more testing is done
        """

        if not late_disbursements:
            return {"message": "No recipients found for disbursement"}

        # Process disbursements by user
        user_disbursement_map = defaultdict(list)
        for disbursement, rotation_order in late_disbursements:
            user_disbursement_map[disbursement.late_recipient_id].append(
                (disbursement, rotation_order)
            )

        for user_id, disbursement_pairs in user_disbursement_map.items():
            total_to_disburse = 0
            try:
                with db.begin_nested():  # Begin atomic transaction for each user
                    for disbursement, rotation_order in disbursement_pairs:
                        activity_id = disbursement.activity_id
                        chama_id = disbursement.chama_id
                        amount = disbursement.late_contribution

                        # Lock and update activity and chama account balances
                        activity_account = (
                            db.query(models.Activity_Account)
                            .filter(models.Activity_Account.activity_id == activity_id)
                            .with_for_update()
                            .first()
                        )

                        chama_account = (
                            db.query(models.Chama_Account)
                            .filter(models.Chama_Account.chama_id == chama_id)
                            .with_for_update()
                            .first()
                        )

                        if not activity_account or not chama_account:
                            raise HTTPException(
                                status_code=404, detail="Account not found"
                            )

                        if (
                            chama_account.account_balance < amount
                            or activity_account.account_balance < amount
                        ):
                            raise HTTPException(
                                status_code=400,
                                detail="Insufficient funds in chama or activity account",
                            )

                        # Deduct from accounts
                        activity_account.account_balance -= amount
                        chama_account.account_balance -= amount
                        total_to_disburse += amount

                        # Update rotation order
                        rotation_order.received_amount += amount
                        rotation_order.fulfilled = (
                            rotation_order.received_amount
                            >= rotation_order.expected_amount
                        )

                    # Mark disbursements as completed for this user
                    db.query(models.LateRotationDisbursements).filter(
                        models.LateRotationDisbursements.late_recipient_id == user_id,
                        models.LateRotationDisbursements.disbursement_completed
                        == False,
                    ).update(
                        {"disbursement_completed": True}, synchronize_session=False
                    )

                    # Update user's wallet balance
                    user_wallet = (
                        db.query(models.User)
                        .filter(models.User.id == user_id)
                        .with_for_update()
                        .first()
                    )

                    if not user_wallet:
                        raise HTTPException(
                            status_code=404, detail="Recipient not found"
                        )

                    user_wallet.wallet_balance += total_to_disburse

                # Commit transaction for the user
                print(f"====committing transaction for user {user_id}====")
                db.commit()

            except Exception as e:
                # Rollback for this user and log error
                print(f"====rolling back transaction for user {user_id}====")
                db.rollback()
                management_error_logger.error(
                    f"Failed to disburse funds for user {user_id}, error: {e}"
                )
                continue  # Skip to the next user

        return {"message": "Funds disbursed successfully"}

    except HTTPException as http_exc:
        management_error_logger.error(f"Failed to disburse funds, error: {http_exc}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Failed to disburse funds, error: {exc}")
        raise HTTPException(status_code=400, detail="Failed to disburse funds")


# manager activitating allowing users to add shares to the activity (merry-go-round)
@router.post(
    "/allow_members_to_increase_shares/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def allow_members_to_increase_shares(
    activity_id: int,
    adjustment_data: schemas.merryGoRoundShareIncrease = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        if activity.activity_type != "merry-go-round":
            raise HTTPException(
                status_code=400, detail="Activity is not a merry-go-round"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not allowed to activate share increase"
            )

        # check if there is an already active record in the MerryGoRoundShareIncrease table, by checking if the deadline is in the future and
        # the allow_share_increase is true
        active_share_increase = (
            db.query(models.MerryGoRoundShareAdjustment)
            .filter(
                and_(
                    models.MerryGoRoundShareAdjustment.activity_id == activity_id,
                    models.MerryGoRoundShareAdjustment.deadline > datetime.now(nairobi_tz),
                    models.MerryGoRoundShareAdjustment.allow_share_increase == True,
                )
            )
            .first()
        )

        if active_share_increase:
            raise HTTPException(
                status_code=400, detail="Share increase is already active"
            )

        # get the current cycle number for the activity
        cycle_number = chama_activity.current_activity_cycle()
        if not cycle_number or cycle_number == 0:
            raise HTTPException(
                status_code=400, detail="No rotation order has been created yet"
            )

        print(" =======setting share increase======")
        # insert the share increase data into the database
        share_increase_activation = models.MerryGoRoundShareAdjustment(
            activity_id=activity_id,
            max_shares = adjustment_data.max_no_shares,
            allow_share_increase = True,
            allow_share_reduction = False,
            allow_new_members = False,
            cycle_number=cycle_number,
            activity_amount=activity.activity_amount,
            adjustment_fee = adjustment_data.adjustment_fee,
            deadline=datetime.strptime(adjustment_data.deadline_date, "%Y-%m-%d"),
        )

        db.add(share_increase_activation)
        db.commit()

        return {"message": "Share increase activated successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Failed to activate share increase, error: {exc}")
        raise HTTPException(
            status_code=400, detail="Failed to activate share increase"
        )

# now we allow new members to join the merry-go-round
@router.post(
    "/allow_new_members_to_join/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def allow_new_members_to_join(
    activity_id: int,
    adjustment_data: schemas.merryGoRoundShareIncrease = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        today = datetime.now(nairobi_tz).date()
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        if activity.activity_type != "merry-go-round":
            raise HTTPException(
                status_code=400, detail="Activity is not a merry-go-round"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not allowed to allow new members to join"
            )

        # check if there is an already active record in the MerryGoRoundShareIncrease table, by checking if the deadline is in the future and
        # the allow_new_members is true
        active_share_increase = (
            db.query(models.MerryGoRoundShareAdjustment)
            .filter(
                and_(
                    models.MerryGoRoundShareAdjustment.activity_id == activity_id,
                    func.date(models.MerryGoRoundShareAdjustment.deadline) > today,
                    models.MerryGoRoundShareAdjustment.allow_new_members == True,
                )
            )
            .first()
        )

        if active_share_increase:
            raise HTTPException(
                status_code=400, detail="New members are already allowed to join"
            )

        # get the current cycle number for the activity
        cycle_number = chama_activity.current_activity_cycle()
        if not cycle_number or cycle_number == 0:
            raise HTTPException(
                status_code=400, detail="No rotation order has been created yet"
            )

        # insert the share increase data into the database
        share_increase_activation = models.MerryGoRoundShareAdjustment(
            activity_id=activity_id,
            max_shares = adjustment_data.max_no_shares,
            allow_share_increase = False,
            allow_share_reduction = False,
            allow_new_members = True,
            cycle_number=cycle_number,
            activity_amount=activity.activity_amount,
            adjustment_fee = adjustment_data.adjustment_fee,
            deadline = datetime.strptime(adjustment_data.deadline_date, "%Y-%m-%d"),
        )

        db.add(share_increase_activation)
        db.commit()

        return {"message": "New members allowed to join successfully"}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Failed to allow new members to join, error: {exc}")
        raise HTTPException(
            status_code=400, detail="Failed to allow new members to join"
        )


# manager deleting an activity, this is what will happen when the manager deletes an activity:
# the actvity will be marked as deleted, the rotation order will be marked as deleted, the activity contribution dates will be mark activity_is_active as false, activity account will be marked as deleted
# all activities_user association table records will mark activity_is_active as false and will delete all auto_contribution records for this activity
@router.delete(
    "/delete_activity/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_activity(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        activity = await get_active_activity_by_id(activity_id, db)
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not allowed to delete this activity"
            )

        with db.begin_nested():
            # mark the activity as deleted
            activity.is_deleted = True
            activity.is_active = False
            activity.deleted_at = today

            # mark the rotation order as deleted
            # db.query(models.RotationOrder).filter(
            #     models.RotationOrder.activity_id == activity_id
            # ).update({"is_deleted": True}, synchronize_session=False)

            # mark the activity contribution dates as inactive
            db.query(models.ActivityContributionDate).filter(
                models.ActivityContributionDate.activity_id == activity_id
            ).update({"activity_is_active": False}, synchronize_session=False)

            # mark the activity account as deleted
            db.query(models.Activity_Account).filter(
                models.Activity_Account.activity_id == activity_id
            ).update({"is_deleted": True}, synchronize_session=False)

            # mark all activities_user association table records as inactive
            db.query(models.activity_user_association).filter(
                models.activity_user_association.c.activity_id == activity_id
            ).update({"activity_is_active": False, "activity_is_deleted": True}, synchronize_session=False)

            # delete all auto_contribution records for this activity
            db.query(models.AutoContribution).filter(
                models.AutoContribution.activity_id == activity_id
            ).delete()

        db.commit()
        return {"message": "Activity deleted successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Failed to delete activity, error: {exc}")
        raise HTTPException(status_code=400, detail="Failed to delete activity")


# transfer fines from activty to manager wallet - update wallet bal, activty account bal and chama account bal
@router.post(
    "/transfer_fines/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def transfer_fines_to_manager_wallet(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).date()
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not allowed to transfer fines"
            )

        # get the fines for the activity
        collected_fines = chama_activity.fines_available_for_transfer()

        if not collected_fines:
            return {"message": "No fines to transfer"}

        # begin transaction block for atomicity
        with db.begin_nested():
            # record the fines transfer
            db.add(models.ManagerFinesTranser(
                manager_id = current_user.id,
                activity_id = activity_id,
                amount = collected_fines,
                transfer_date = today,
                current_cycle = chama_activity.current_activity_cycle()
            ))


            # update the manager's wallet balance
            manager_wallet = (
                db.query(models.User)
                .filter(models.User.id == current_user.id)
                .with_for_update()
                .first()
            )

            if not manager_wallet:
                raise HTTPException(status_code=404, detail="Manager not found")

            manager_wallet.wallet_balance += collected_fines

            # update the activity account balance
            activity_account = (
                db.query(models.Activity_Account)
                .filter(models.Activity_Account.activity_id == activity_id)
                .with_for_update()
                .first()
            )

            if not activity_account:
                raise HTTPException(status_code=404, detail="Activity account not found")

            activity_account.account_balance -= collected_fines

            # update the chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == activity.chama_id)
                .with_for_update()
                .first()
            )

            if not chama_account:
                raise HTTPException(status_code=404, detail="Chama account not found")

            chama_account.account_balance -= collected_fines

        db.commit()
        last_contribution_date = chama_activity.activity_dates()["last_contribution_date"]
        if today > last_contribution_date:
            # if the disbursemnet is after the last contribution date, initiate the final fines transfer to the manager's wallet
            initiaite_final_fines_transfer_to_manager_wallet.delay(activity_id, collected_fines, current_user.id)

        return {"message": "Fines transferred successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Failed to transfer fines, error: {exc}")
        raise HTTPException(status_code=400, detail="Failed to transfer fines")