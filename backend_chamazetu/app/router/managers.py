from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytz, logging
from sqlalchemy import func, update, and_, table, column, desc

from .date_functions import (
    calculate_custom_interval,
    calculate_monthly_interval,
    calculate_daily_interval,
    calculate_weekly_interval,
    calculate_monthly_same_day_interval,
)
from .. import schemas, database, utils, oauth2, models

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
            .filter(models.ActivityContributionDate.chama_id == group_id)
            .order_by(desc(models.ActivityContributionDate.next_contribution_date))
            .all()
        )

        # total unpaid fines
        total_fines = (
            db.query(func.coalesce(func.sum(models.ActivityFine.expected_repayment), 0))
            .filter(
                and_(
                    models.ActivityFine.chama_id == group_id,
                    models.ActivityFine.is_paid == False,
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
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
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

        cycle_number = (
            db.query(func.coalesce(func.max(models.RotationOrder.cycle_number), 0))
            .filter(models.RotationOrder.activity_id == activity_id)
            .scalar()
        )
        if cycle_number == 0:
            cycle_number = 1
        else:
            cycle_number += 1

        share_value = activity.activity_amount
        frequency = activity.frequency
        interval = activity.interval
        contribution_day = activity.contribution_day
        first_contribution_date = activity.first_contribution_date

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
                    models.activity_user_association.c.is_active == True,
                )
            )
            .all()
        )

        if not users:
            raise HTTPException(
                status_code=404, detail="No users found in the activity"
            )

        number_of_activity_users = len(users)
        number_of_shares = sum([user.shares for user in users])
        expected_receiving_amount = number_of_shares * share_value

        # create a rotation order for each user in the activity
        rotation_order = []

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

        # we will now include the receiving date for each user in the rotation order as well as their order_in_rotation number(1, 2 ...),
        # the dates will follow the frequency and interval of the activity
        # TODO: update the cycle to check if there is a record already, if not the cycle is 1, if there is a record, the cycle is the last cycle + 1

        set_contribution_date = first_contribution_date
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
        raise e
    except Exception as e:
        db.rollback()
        management_error_logger.error(
            f"failed to create rotation order for chama, error: {e}"
        )
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
        activity = (
            db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        )
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
                    == next_contribution_date,
                )
            )
            .scalar()
        )

        if not pooled_amount:
            raise HTTPException(
                status_code=404, detail="No pooled amount found for disbursement"
            )

        # TODO: for testing purposes, we will not check the date we will just go on, later enforce to ensure the contribution/rotation date is passed.
        # if today < previous_contribution_date:
        #     raise HTTPException(
        #         status_code=400,
        #         detail="Cannot disburse funds before the previous contribution date",
        #     )

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

        # TODO: for testing we will use next_contribution_date, later we will use previous_contribution_date
        recipient = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.receiving_date == next_contribution_date,
                    models.RotationOrder.cycle_number == cycle_number,
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
