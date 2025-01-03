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
from sqlalchemy import func, update, and_, table, column, desc, select, insert, Float

from .. import schemas, database, utils, oauth2, models
from .chama_and_activity_classes import chamaActivity

router = APIRouter(prefix="/activities", tags=["activities"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")


# function that gets an activity by id
async def get_active_activity_by_id(activity_id: int, db: Session):
    return (
        db.query(models.Activity)
        .filter(
            and_(
                models.Activity.id == activity_id,
                models.Activity.is_deleted == False,
                models.Activity.is_active == True,
            )
        )
        .first()
    )

async def get_active_user_in_activity(activity_id: int, user_id: int, db: Session):
    return (
        db.query(models.activity_user_association)
        .filter(
            and_(
                models.activity_user_association.c.activity_id == activity_id,
                models.activity_user_association.c.user_id == user_id,
                models.activity_user_association.c.user_is_active == True,
            )
        )
        .first()
    )


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


            # create a cycle number for the activity
            first_cycle_number = models.ActivityCycle(
                activity_id=new_activity.id, cycle_number=1
            )
            db.add(first_cycle_number)

            # if actvity table-banking, create a loan management and table banking dividends accounts
            if activity_data["activity_type"] == "table-banking":
                loan_management_entry = models.TableBankingLoanManagement(
                    activity_id=new_activity.id, total_loans_taken=0.0, unpaid_loans=0.0, paid_loans=0.0, unpaid_interest=0.0, paid_interest=0.0, cycle_number=1
                )
                db.add(loan_management_entry)

                table_banking_dividends_entry = models.TableBankingDividend(
                    chama_id=activity_data["chama_id"], activity_id=new_activity.id, unpaid_dividends=0.0, paid_dividends=0.0, cycle_number=1
                )
                db.add(table_banking_dividends_entry)

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

# retrieve the chama_name, chama_id, activity_type from activity_id
@router.get(
    "/details/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_activity_detail(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()     

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        chama = (
            db.query(models.Chama)
            .filter(models.Chama.id == activity.chama_id)
            .first()
        )
        if not chama:
            raise HTTPException(
                status_code=404, detail="Chama not found or does not exist"
            )

        return {
            "chama_name": chama.chama_name,
            "chama_id": chama.id,
            "activity_type": activity.activity_type,
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to get activity properties: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get activity properties: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve activity properties")


# retrieve an activity by id as a manager
@router.get(
    "/manager/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_activity_by_id(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        account = chama_activity.activity_account_balance()
        if not account:
            account = 0.0

        next_contribution_date = chama_activity.previous_and_upcoming_contribution_dates()[
            "next_contribution_date"
        ]

        missed_contributions = chama_activity.current_cycle_unpaid_fines_and_missed_amount()["total_unpaid"]

        paid_fines = 0
        if chama_activity.activity_type == "merry-go-round":
            paid_fines = chama_activity.merry_go_round_max_cycle()
        else:
            paid_fines = chama_activity.current_cycle_paid_fines()

        rotation_contributions_resp = []
        unpaid_loans = 0
        if activity.activity_type == "merry-go-round":
            rotation_contributions = (
                db.query(
                    models.RotatingContributions,
                    models.User.first_name,
                    models.User.last_name,
                )
                .join(
                    models.User,
                    models.User.id == models.RotatingContributions.contributor_id,
                )
                .filter(
                    and_(
                        models.RotatingContributions.activity_id == activity_id,
                        models.RotatingContributions.rotation_date
                        == next_contribution_date,
                        models.RotatingContributions.cycle_number == chama_activity.merry_go_round_max_cycle()
                    )
                )
                .all()
            )

            if rotation_contributions:
                rotation_contributions_resp = [
                    {
                        "contributor_name": f"{contribution.first_name} {contribution.last_name}",
                        "expected_amount": contribution.RotatingContributions.expected_amount,
                        "contributed_amount": contribution.RotatingContributions.contributed_amount,
                        "fine": contribution.RotatingContributions.fine,
                        "rotation_date": contribution.RotatingContributions.rotation_date.strftime(
                            "%d-%B-%Y"),
                        "cycle_number": contribution.RotatingContributions.cycle_number,
                        "contributing_share": contribution.RotatingContributions.contributing_share,
                        "recipient_share": contribution.RotatingContributions.recipient_share,
                    }
                    for contribution in rotation_contributions
                ]


        if activity.activity_type == "table-banking":
            cycle_number = chama_activity.current_activity_cycle()

            loans_data = db.query(models.TableBankingLoanManagement).filter(
                models.TableBankingLoanManagement.activity_id == activity_id,
                models.TableBankingLoanManagement.cycle_number == cycle_number
                ).first()

            unapproved_loans = db.query(models.TableBankingRequestedLoans).filter(
                models.TableBankingRequestedLoans.activity_id == activity_id,
                models.TableBankingRequestedLoans.loan_approved == False,
                models.TableBankingRequestedLoans.loan_cleared == False,
                models.TableBankingRequestedLoans.cycle_number == cycle_number,
                models.TableBankingRequestedLoans.rejected == False,
            ).count()

            # dividend so far
            dividend_data = db.query(models.TableBankingDividend).filter(
                models.TableBankingDividend.activity_id == activity_id,
                models.TableBankingDividend.cycle_number == cycle_number
            ).first()

            # sum of paid fines so far
            paid_fines = db.query(func.coalesce(func.sum(models.ActivityFine.fine), 0)).filter(
                models.ActivityFine.activity_id == activity_id,
                models.ActivityFine.is_paid == True,
            ).scalar()

        activity = {
            "chama_id": activity.chama_id,
            "activity_name": activity.activity_title,
            "activity_type": activity.activity_type,
            "activity_amount": activity.activity_amount,
            "activity_balance": account,
            "activity_id": activity,
            "unpaid_loans": loans_data.unpaid_loans + loans_data.unpaid_interest if activity.activity_type == "table-banking" else 0,
            "total_loans_taken": loans_data.total_loans_taken if activity.activity_type == "table-banking" else 0,
            "unapproved_loans": unapproved_loans if activity.activity_type == "table-banking" else 0,
            "cycle_number": cycle_number if activity.activity_type == "table-banking" else 0,
            "unpaid_dividends": dividend_data.unpaid_dividends if activity.activity_type == "table-banking" else 0,
            "missed_contributions": missed_contributions,
            "paid_fines": paid_fines,
        }

        return {
            "upcoming_contribution_date": next_contribution_date.strftime("%d-%B-%Y"),
            "activity": activity,
            "rotation_contributions": rotation_contributions_resp,
        }
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
        today = datetime.now(nairobi_tz).date()
        activities = (
            db.query(models.Activity)
            .filter(
                and_(
                    models.Activity.chama_id == chama_id,
                    models.Activity.is_deleted == False,
                    models.Activity.is_active == True,
                )
            )
            .all()
        )

        if not activities:
            return {
                "status": "success",
                "message": "No activities found for this chama",
            }

        activities_ids = [activity.id for activity in activities]

        active_late_joining_activities = db.query(models.MerryGoRoundShareAdjustment).filter(
            and_(
                models.MerryGoRoundShareAdjustment.activity_id.in_(activities_ids),
                func.date(models.MerryGoRoundShareAdjustment.deadline) >= today,
            )
        ).all()

        active_late_joining_activities_ids = [
            activity.activity_id for activity in active_late_joining_activities
        ]

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
                "joining_closed": today > activity.last_joining_date.date(),
                "late_joining_open": activity.id in active_late_joining_activities_ids,
            }
            activities_list.append(activity)
        return activities_list
    except HTTPException as e:
        management_error_logger.error(f"Failed to get all activities: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get all activities: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve all activities")


# set an activities final contribution date
@router.put(
    "/last_contribution_date/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def set_last_contrbution_date(
    activity_id: int,
    final_contribution_date: schemas.LastContributionDate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        last_contribution_date = datetime.strptime(
            final_contribution_date.last_contribution_date, "%Y-%m-%d"
        )
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if current_user.id != activity.manager_id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        current_cycle = chama_activity.current_activity_cycle()

        final_contribution_date = (
            db.query(models.LastContributionDate)
            .filter(
                and_(
                    models.LastContributionDate.activity_id == activity_id,
                    models.LastContributionDate.cycle_number == current_cycle,
                )
            )
            .first()
        )

        if final_contribution_date:
            final_contribution_date.last_contribution_date = last_contribution_date
            final_contribution_date.updated_at = today
        else:
            # we create a new final contribution date
            new_final_contribution_date = models.LastContributionDate(
                activity_id=activity_id,
                last_contribution_date=last_contribution_date,
                cycle_number=current_cycle,
                updated_at=today,
            )
            db.add(new_final_contribution_date)

        db.commit()
        return {"status": "success", "message": "Final contribution date set successfully"}
    except HTTPException as e:
        management_error_logger.error(f"Failed to set final contribution date: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to set final contribution date: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to set final contribution date"
        )


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
        today = datetime.now(nairobi_tz).date()
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        late_joining_open = db.query(models.MerryGoRoundShareIncrease).filter(
            and_(
                models.MerryGoRoundShareIncrease.activity_id == activity_id,
                func.date(models.MerryGoRoundShareIncrease.deadline) >= today,
            )
        ).first()

        # prevent joining if tday is past activity's last joining date
        if not late_joining_open and today > activity.last_joining_date.date():
            raise HTTPException(status_code=400, detail="You cannot join this activity")

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
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
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

        account_balance = chama_activity.activity_account_balance()

        ## sum todays contributions to this activity
        today = datetime.now(nairobi_tz).date()
        today_contributions = chama_activity.todays_contributions()

        contrib_dates = chama_activity.previous_and_upcoming_contribution_dates()
        if not contrib_dates:
            raise HTTPException(
                status_code=400, detail="Failed to get contribution dates"
            )

        next_contribution_date = contrib_dates["next_contribution_date"]
        prev_contribution_date = contrib_dates["previous_contribution_date"]

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
            "admin_fee": activity.admin_fee,
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
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
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

        account_balance = chama_activity.activity_account_balance()

        # if this is a table-banking activity, fetch loans data for user
        personal_loan = 0
        if activity.activity_type == "table-banking":
            personal_loan = (
                db.query(func.coalesce(func.sum(models.TableBankingRequestedLoans.total_required), 0))
                .filter(
                    models.TableBankingRequestedLoans.user_id == current_user.id,
                    models.TableBankingRequestedLoans.activity_id == activity_id,
                    models.TableBankingRequestedLoans.loan_approved == True,
                    models.TableBankingRequestedLoans.loan_cleared == False,
                )
                .scalar()
                or 0
            )

        ## sum todays contributions to this activity
        today = datetime.now(nairobi_tz).date()
        today_contributions = chama_activity.todays_contributions()

        contrib_dates = chama_activity.previous_and_upcoming_contribution_dates()
        if not contrib_dates:
            raise HTTPException(
                status_code=400, detail="Failed to get contribution dates"
            )

        next_contribution_date = contrib_dates["next_contribution_date"]
        prev_contribution_date = contrib_dates["previous_contribution_date"]

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
            "personal_loan": personal_loan,
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
            "admin_fee": activity.admin_fee,
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
                    models.ActivityContributionDate.activity_is_active == True,
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
                    models.ActivityContributionDate.activity_is_active == True,
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
                models.activity_user_association.c.admin_fee,
            )
            .filter(
                and_(
                    models.activity_user_association.c.activity_id.in_(activity_ids),
                    models.activity_user_association.c.user_is_active == True,
                    models.activity_user_association.c.activity_is_deleted == False,
                    models.activity_user_association.c.activity_is_active == True,
                )
            )
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
            # get this activtiy  current cycle
            chama_activity = chamaActivity(db, activity.activity_id)
            current_cycle = chama_activity.current_activity_cycle()
            if not current_cycle or current_cycle == 0:
                continue

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
                expected_contribution = user.share_value * user.shares + (user.admin_fee * user.shares)
                missed_amount = expected_contribution - total_contribution

                if missed_amount > 0:
                    fine = activity.fine * user.shares

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
                            "cycle_number": current_cycle,
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
    except HTTPException as http_exc:
        management_error_logger.error(f"Failed to set fines: {http_exc}")
        raise http_exc
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
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

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
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

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
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

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
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

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


# retrieve the rotation order of an activity
@router.get(
    "/rotation_order/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def activity_rotation_order(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        today = datetime.now(nairobi_tz).date()
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .scalar()
        )

        if not next_contribution_date:
            raise HTTPException(
                status_code=404, detail="Next contribution date not found"
            )

        cycle_number = chama_activity.merry_go_round_max_cycle()


        # if this activity latest cycle number largest/latest date is behind the current date, then we need to create a new set of rotatiion_order records
        final_rotation_date = (
            db.query(func.max(models.RotationOrder.receiving_date))
            .filter(
                models.RotationOrder.activity_id == activity_id,
                models.RotationOrder.cycle_number == cycle_number,
            )
            .scalar()
        )

        if final_rotation_date is None or final_rotation_date.date() < today:
            return {
                "pooled_so_far": 0,
                "activity_name": activity.activity_title,
                "activity_id": activity.id,
                "upcoming_recipient": {},
                "rotation_order": [],
                "rotation_date": None,
                "new_rotation_needed": False if final_rotation_date is None else True,
            }

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
                    == next_contribution_date,
                    models.RotatingContributions.cycle_number == cycle_number,
                )
            )
            .scalar()
        )

        # query to retrieve the rotation orders with the latest cycle_number, we will include their names from user tablem and ordeR_in_rotation, share_name, payout_date and rotation_status from RotationOrder
        activity_rotation_order = (
            db.query(
                models.RotationOrder.cycle_number,
                models.RotationOrder.order_in_rotation,
                models.RotationOrder.share_name,
                models.RotationOrder.receiving_date,
                models.RotationOrder.fulfilled,
                models.User.first_name,
                models.User.last_name,
                models.User.profile_picture,
            )
            .join(models.User, models.User.id == models.RotationOrder.recipient_id)
            .filter(
                models.RotationOrder.activity_id == activity_id,
                models.RotationOrder.cycle_number == cycle_number,
            )
            .order_by(models.RotationOrder.order_in_rotation)
            .all()
        )

        if not activity_rotation_order:
            return {
                "pooled_so_far": pooled_so_far,
                "activity_name": activity.activity_title,
                "activity_id": activity.id,
                "upcoming_recipient": {},
                "rotation_order": [],
                "rotation_date": next_contribution_date.strftime("%d-%B-%Y"),
                "new_rotation_needed": False,
            }

        # retrieve the name of the upcoming receiver using the next contribution date and the RotationOrder table and the User table
        upcoming_recipient = (
            db.query(
                models.User.first_name,
                models.User.last_name,
                models.User.profile_picture,
                models.RotationOrder.expected_amount,
                models.RotationOrder.share_name,
            )
            .join(
                models.RotationOrder,
                models.RotationOrder.recipient_id == models.User.id,
            )
            .filter(
                models.RotationOrder.activity_id == activity_id,
                models.RotationOrder.receiving_date == next_contribution_date,
            )
            .first()
        )

        if not upcoming_recipient:
            raise HTTPException(status_code=404, detail="Upcoming recipient not found")

        # TODO: retrieve pooled so far and some recent transactions if possible

        rotation_order = [
            {
                "cycle_number": order.cycle_number,
                "order_in_rotation": order.order_in_rotation,
                "share_name": order.share_name,
                "receiving_date": order.receiving_date.strftime("%d-%B-%Y"),
                "fulfilled": "Received" if order.fulfilled else "Not Received",
                "user_name": f"{order.first_name} {order.last_name}",
            }
            for order in activity_rotation_order
        ]

        recipient = {
            "user_name": f"{upcoming_recipient.first_name} {upcoming_recipient.last_name}",
            "profile_picture": upcoming_recipient.profile_picture,
            "share_name": upcoming_recipient.share_name,
            "expected_amount": upcoming_recipient.expected_amount,
        }

        return {
            "pooled_so_far": pooled_so_far,
            "activity_name": activity.activity_title,
            "activity_id": activity.id,
            "upcoming_recipient": recipient,
            "rotation_order": rotation_order,
            "rotation_date": next_contribution_date.strftime("%d-%B-%Y"),
            "new_rotation_needed": False,
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to get activity rotation order: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get activity rotation order: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to retrieve activity rotation order"
        )


# here we will create fresh rotation contributions for the upcoming rotation date
# this will run after the activities contributions dates have been updated and will focus on merry-go-rounds only-a little after midnight
"""
 id | chama_id | activity_id | contributor_id | recipient_id | recipient_share | contributing_share | expected_amount | contributed_amount | fine | rotation_date | cycle_number 
----+----------+-------------+----------------+--------------+-----------------+--------------------+-----------------+--------------------+------+---------------+--------------
"""


@router.post(
    "/create_rotation_contributions",
    status_code=status.HTTP_201_CREATED,
)
async def create_rotation_contributions(
    db: Session = Depends(database.get_db),
):
    try:
        print("==========NEW creating rotation contributions================")
        # get merry-go-round activities that need a new set of records in the rotation contribution tracker
        today = datetime.now(nairobi_tz).date()
        Activity = aliased(models.Activity)
        ActivityContributionDate = aliased(models.ActivityContributionDate)
        RotationOrder = aliased(models.RotationOrder)
        RotatingContributions = aliased(models.RotatingContributions)

        # subquery to get the max cycle_number for each activity
        subquery_one = (
            db.query(
                RotationOrder.activity_id,
                func.max(RotationOrder.cycle_number).label("max_cycle_number"),
            )
            .group_by(RotationOrder.activity_id)
            .subquery()
        )

        # main queryy to get the activities whose highest cycle has a receiving_date not past today
        results_one = (
            db.query(RotationOrder.activity_id)
            .join(
                subquery_one,
                (RotationOrder.activity_id == subquery_one.c.activity_id)
                & (RotationOrder.cycle_number == subquery_one.c.max_cycle_number),
            )
            .filter(func.date(RotationOrder.receiving_date) >= today)
            .distinct()
            .all()
        )

        # list of distinct activity_ids whose highest cycle_number's receiving_date is not past today
        activities_with_rotation_order = [result.activity_id for result in results_one]

        if not activities_with_rotation_order:
            return {
                "status": "success",
                "message": "No activities with rotation order",
            }

        activities = (
            db.query(Activity)
            .join(
                ActivityContributionDate,
                and_(
                    Activity.id == ActivityContributionDate.activity_id,
                    Activity.chama_id == ActivityContributionDate.chama_id,
                ),
            )
            .outerjoin(
                RotatingContributions,
                and_(
                    Activity.id == RotatingContributions.activity_id,
                    Activity.chama_id == RotatingContributions.chama_id,
                    RotatingContributions.rotation_date
                    == ActivityContributionDate.next_contribution_date,
                ),
            )
            .filter(
                and_(
                    # ensure the activity has no rotation contributions for the upcoming rotation date
                    RotatingContributions.activity_id == None,
                    ActivityContributionDate.activity_type == "merry-go-round",
                    # ensure the activity has a rotation order
                    Activity.id.in_(activities_with_rotation_order),
                    Activity.is_active == True,
                    Activity.is_deleted == False,

                ),
            )
            .all()
        )

        if not activities:
            return {
                "status": "success",
                "message": "No activities in need of new rotation contributions",
            }

        print("==========activities found================")
        # for activity in activities:
        #     print(activity.activity_title)
        #     print()

        # get actvity ids
        print("====activities ids====")
        activity_ids = [activity.id for activity in activities]

        # this will get the highest cycle number for each activity
        cycle_numbers = (
            db.query(RotationOrder.activity_id, func.max(RotationOrder.cycle_number))
            .filter(RotationOrder.activity_id.in_(activity_ids))
            .group_by(RotationOrder.activity_id)
            .all()
        )
        # {activity_id:1, cycle_number: 1}

        cycle_numbers_dict = [
            {"activity_id": cycle[0], "cycle_number": cycle[1]}
            for cycle in cycle_numbers
        ]

        # get the upcoming rotation contribution date from the activity contribution date table as the next contribution date for all the activities
        activities_next_contribution_dates = (
            db.query(ActivityContributionDate)
            .filter(ActivityContributionDate.activity_id.in_(activity_ids))
            .all()
        )
        if not activities_next_contribution_dates:
            return {
                "status": "success",
                "message": "No activities next contribution dates found",
            }
        rotation_dates = [
            {
                "activity_id": date.activity_id,
                "rotation_date": date.next_contribution_date,
            }
            for date in activities_next_contribution_dates
        ]


        # get the upcoming recipients for the activities by using the next contribution date and the RotationOrder table
        upcoming_recipients = (
            db.query(RotationOrder)
            .filter(
                RotationOrder.activity_id.in_(activity_ids),
                RotationOrder.receiving_date.in_(
                    [date["rotation_date"] for date in rotation_dates]
                ),
            )
            .all()
        )

        if not upcoming_recipients:
            return {
                "status": "success",
                "message": "No upcoming recipients found",
            }

        upcoming_recipients_dict = [
            {
                "activity_id": recipient.activity_id,
                "recipient_id": recipient.recipient_id,
                "share_name": recipient.share_name,
                "expected_amount": recipient.expected_amount,
                "rotation_date": recipient.receiving_date,
            }
            for recipient in upcoming_recipients
        ]


        activities_users = (
            db.query(RotationOrder)
            .filter(
                and_(
                    RotationOrder.activity_id.in_(activity_ids),
                    RotationOrder.cycle_number.in_(
                        [cycle["cycle_number"] for cycle in cycle_numbers_dict]
                    ),
                )
            )
            .all()
        )

        if not activities_users:
            print("=====no activities users found======")
            return {
                "status": "success",
                "message": "No activities users found",
            }

        print("=====activities users resp======")
        activities_users_resp = [
            {
                "chama_id": activity.chama_id,
                "activity_id": activity.activity_id,
                "contributor_id": activity.recipient_id,
                "contributing_share": activity.share_name,
                "expected_amount": activity.share_value,
                "contributed_amount": 0,
                "fine": 0,
                "cycle_number": next(
                    cycle["cycle_number"]
                    for cycle in cycle_numbers_dict
                    if cycle["activity_id"] == activity.activity_id
                ),
                "recipient_id": next(
                    recipient["recipient_id"]
                    for recipient in upcoming_recipients_dict
                    if recipient["activity_id"] == activity.activity_id
                ),
                "recipient_share": next(
                    recipient["share_name"]
                    for recipient in upcoming_recipients_dict
                    if recipient["activity_id"] == activity.activity_id
                ),
                "rotation_date": next(
                    recipient["rotation_date"]
                    for recipient in upcoming_recipients_dict
                    if recipient["activity_id"] == activity.activity_id
                ),
            }
            for activity in activities_users
        ]
        # print(activities_users_resp)

        print(" =====you have crossed the return point=====")

        # perform bulk insert of the new rotation contributions
        if activities_users_resp:
            print("=====inserting activities users with rotation date======")
            with db.begin_nested():
                db.bulk_insert_mappings(
                    models.RotatingContributions, activities_users_resp
                )

            db.commit()

        print("==========past the bulk insetion===============")
        return {
            "status": "success",
            "message": "Activities found",
        }
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Failed to create rotation contributions(http error): {http_exc}"
        )
        raise http_exc
    except Exception as e:
        management_error_logger.error(
            f"Failed to create rotation contributions(exception error): {str(e)}"
        )
        raise HTTPException(
            status_code=400, detail=f"Failed to create rotation contributions {str(e)}"
        )


# redo the above route for one activity only
@router.post(
    "/create_activity_rotation_contributions/{activity_id}",
    status_code=status.HTTP_201_CREATED,
)
async def create_rotation_contribution_for_activity(
    activity_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        chama_activity = chamaActivity(db, activity_id)
        activity =chama_activity.activity()

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        # get the upcoming rotation contribution date from the activity contribution date table as the next contribution date for all the activities
        activity_next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(
                models.ActivityContributionDate.activity_id == activity_id,
                models.ActivityContributionDate.activity_type == "merry-go-round",
            )
            .first()
        )

        if not activity_next_contribution_date:
            raise HTTPException(
                status_code=404, detail="Next contribution date not found"
            )

        rotation_date = activity_next_contribution_date.next_contribution_date

        # get the upcoming recipient for the activity by using the next contribution date and the RotationOrder table
        upcoming_recipient = (
            db.query(models.RotationOrder)
            .filter(
                models.RotationOrder.activity_id == activity_id,
                models.RotationOrder.receiving_date == rotation_date,
            )
            .first()
        )

        if not upcoming_recipient:
            raise HTTPException(status_code=404, detail="Upcoming recipient not found")

        # get the cycle number for the activity
        cycle_number = chama_activity.merry_go_round_max_cycle()

        # get the users for the activity with the cycle number
        activity_users = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                )
            )
            .all()
        )

        if not activity_users:
            raise HTTPException(status_code=404, detail="Activity users not found")

        activities_users_resp = [
            {
                "chama_id": activity.chama_id,
                "activity_id": activity_id,
                "contributor_id": user.recipient_id,
                "contributing_share": user.share_name,
                "expected_amount": user.share_value,
                "contributed_amount": 0,
                "fine": 0,
                "cycle_number": cycle_number,
                "recipient_id": upcoming_recipient.recipient_id,
                "recipient_share": upcoming_recipient.share_name,
                "rotation_date": rotation_date,
            }
            for user in activity_users
        ]

        # perform bulk insert of the new rotation contributions
        if activities_users_resp:
            with db.begin_nested():
                db.bulk_insert_mappings(
                    models.RotatingContributions, activities_users_resp
                )

            db.commit()

        return {
            "status": "success",
            "message": "Rotation contributions created successfully",
        }
    except HTTPException as e:
        management_error_logger.error(
            f"Failed to create rotation contributions for activity: {e}"
        )
        raise e
    except Exception as e:
        management_error_logger.error(
            f"Failed to create rotation contributions for activity: {e}"
        )
        raise HTTPException(
            status_code=400,
            detail="Failed to create rotation contributions for activity",
        )


# retrieve all members with the fines in a certain activity
@router.get(
    "/fines/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_activity_fines(
    activity_id: int,
    dates: schemas.TableBankingLoanHistory = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity_is_active()

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        from_date = datetime.strptime(dates.from_date, "%Y-%m-%d").date()
        to_date = datetime.strptime(dates.to_date, "%Y-%m-%d").date()
        

        # fetch all the fines in this activity
        fines = (
            db.query(
                models.ActivityFine.user_id,
                models.ActivityFine.fine,
                models.ActivityFine.missed_amount,
                models.ActivityFine.expected_repayment,
                models.ActivityFine.fine_date,
                models.ActivityFine.fine_reason,
                models.ActivityFine.is_paid,
                models.User.first_name,
                models.User.last_name,
            )
            .join(models.User, models.User.id == models.ActivityFine.user_id)
            .filter(
                and_(
                    models.ActivityFine.activity_id == activity_id,
                    models.ActivityFine.is_paid == False,
                    models.ActivityFine.fine_date >= from_date,
                    models.ActivityFine.fine_date <= to_date,
                )
            )
            .all()
        )

        fines_list = [
            {
                "user_name": f"{fine.first_name} {fine.last_name}",
                "fine": fine.fine,
                "missed_amount": fine.missed_amount,
                "expected_repayment": fine.expected_repayment,
                "fine_date": fine.fine_date.strftime("%d-%B-%Y"),
                "fine_reason": fine.fine_reason,
                "is_paid": "Cleared" if fine.is_paid else "Not Cleared",
            }
            for fine in fines
        ]

        return fines_list
    except HTTPException as e:
        management_error_logger.error(f"Failed to get activity fines: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get activity fines: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve activity fines")


# updating accepting members for activities to false for those who last joining date is behind today
@router.put(
    "/update_activities_accepting_members",
    status_code=status.HTTP_200_OK,
)
async def update_accepting_members(
    db: Session = Depends(database.get_db),
):
    print("========updating activities accepting members========")
    try:
        today = datetime.now(nairobi_tz).date()

        # get all the activities whose last joining date is behind today
        activities = (
            db.query(models.Activity)
            .filter(
                and_(
                    models.Activity.accepting_members == True,
                    models.Activity.last_joining_date < today,
                )
            )
            .all()
        )

        if not activities:
            return {
                "status": "success",
                "message": "No activities to update",
            }

        # update the accepting_members status to False for all the activities
        for activity in activities:
            activity.accepting_members = False

        db.commit()

        return {
            "status": "success",
            "message": "Accepting members status updated successfully",
        }
    except HTTPException as e:
        management_error_logger.error(
            f"Failed to update accepting members status: {e}"
        )
        raise e
    except Exception as e:
        db.rollback()
        management_error_logger.error(
            f"Failed to update accepting members status: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to update accepting members status"
        )


# get late joining data for merry-go-round activities from MerryGoRoundShareIncrease
@router.get(
    "/late_joining_data/{activity_id}",
    status_code=status.HTTP_200_OK,
)
async def get_late_joining_data(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        today = datetime.now(nairobi_tz).date()

        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        print("===activity===")
        # get the late joining data for the activity
        late_joining_data = db.query(models.MerryGoRoundShareAdjustment).filter(
            and_(
                models.MerryGoRoundShareAdjustment.activity_id == activity_id,
                models.MerryGoRoundShareAdjustment.allow_new_members == True,
                func.date(models.MerryGoRoundShareAdjustment.deadline) >= today,
            )
        ).first()

        if not late_joining_data:
            raise HTTPException(
                status_code=404, detail="Late joining data not found"
            )

        next_contribution_date = (
            db.query(models.ActivityContributionDate.next_contribution_date)
            .filter(
                models.ActivityContributionDate.activity_id == activity_id,
            )
            .scalar()
        )

        # current cycle number
        cycle_number = chama_activity.merry_go_round_max_cycle()

        if not cycle_number:
            raise HTTPException(status_code=404, detail="Cycle number not found")

        # retrieve all rotation order in the current cycle upto the next contribution date
        rotations_to_clear = (
            db.query(models.RotationOrder)
            .filter(
                and_(
                    models.RotationOrder.activity_id == activity_id,
                    models.RotationOrder.cycle_number == cycle_number,
                    models.RotationOrder.receiving_date <= next_contribution_date,
                )
            )
            .all()
        )

        if not rotations_to_clear:
            raise HTTPException(status_code=404, detail="This activity has no rotations")

        return {
            "max_shares": late_joining_data.max_shares,
            "activity_id": activity_id,
            "deadline": late_joining_data.deadline.strftime("%d-%B-%Y"),
            "share_value": activity.activity_amount,
            "adjustment_fee": late_joining_data.adjustment_fee,
            "past_rotations": len(rotations_to_clear) - 1,
            "late_joining_open": today <= late_joining_data.deadline.date(),
        }
    except HTTPException as e:
        management_error_logger.error(f"Failed to get late joining data: {e}")
        raise e
    except Exception as e:
        management_error_logger.error(f"Failed to get late joining data: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve late joining data")

@router.get("/disbursement_records/{activity_id}", status_code=status.HTTP_200_OK)
async def activity_disbursement_records(
    activity_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        # get all the disbursement records for the activity by retrieving all past records in the rotation order behind today
        today = datetime.now(nairobi_tz).date()

        disbursement_records = db.query(models.RotationOrder).filter(
            and_(
                models.RotationOrder.activity_id == activity_id,
                func.date(models.RotationOrder.receiving_date) < today,
            )
        ).all()

        if not disbursement_records:
            disbursement_records = []

        late_disbursement_records = (
            db.query(models.LateRotationDisbursements)
            .filter(
                and_(
                    models.LateRotationDisbursements.activity_id == activity_id,
                    models.LateRotationDisbursements.disbursement_completed == False,
                )
            )
            .all()
        )

        late_recipient_ids = list(set([late_recipient.late_recipient_id for late_recipient in late_disbursement_records]))
        late_contributor_ids = list(set([late_recipient.late_contributor_id for late_recipient in late_disbursement_records]))

        # create a dictionary of the late recipients and contributors with their names
        late_recipients = (
            db.query(models.User)
            .filter(models.User.id.in_(late_recipient_ids))
            .all()
        )

        late_contributors = (
            db.query(models.User)
            .filter(models.User.id.in_(late_contributor_ids))
            .all()
        )

        late_recipients_dict = {late_recipient.id: f"{late_recipient.first_name} {late_recipient.last_name}" for late_recipient in late_recipients}
        late_contributors_dict = {late_contributor.id: f"{late_contributor.first_name} {late_contributor.last_name}" for late_contributor in late_contributors}

        if not late_disbursement_records:
            late_disbursement_records = []

        if not disbursement_records and not late_disbursement_records:
            return {
                "chama_id": activity.chama_id,
                "activity_id": activity_id,
                "disbursement_records": [],
                "late_disbursement_records": [],
            }
        
        if disbursement_records:
            disbursement_records_list = [
                {
                    "cycle_number": record.cycle_number,
                    "order_in_rotation": record.order_in_rotation,
                    "received_amount": record.received_amount,
                    "expected_amount": record.expected_amount,
                    "share_name": record.share_name,
                    "receiving_date": record.receiving_date.strftime("%d-%B-%Y"),
                    "disbursement": "Complete" if record.fulfilled else "Incomplete",
                    "user_name": record.user_name,
                }
                for record in disbursement_records
            ]

        late_disbursement_records_list = []
        if late_disbursement_records:
            late_disbursement_records_list = [
                {
                    "pending_amount": late_record.late_contribution,
                    "missed_date": late_record.missed_rotation_date.strftime("%d-%B-%Y"),
                    "recipient_name": late_recipients_dict[late_record.late_recipient_id],
                    "contributor_name": late_contributors_dict[late_record.late_contributor_id],
                }
                for late_record in late_disbursement_records
            ]

        return {
            "chama_id": activity.chama_id,
            "activity_id": activity_id,
            "expected_amount": disbursement_records[0].expected_amount if disbursement_records else 0,
            "disbursement_records": disbursement_records_list,
            "late_disbursement_records": late_disbursement_records_list,
        }
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Failed to get activity disbursement records(http error): {http_exc}"
        )
        raise http_exc
    except Exception as e:
        management_error_logger.error(
            f"Failed to get activity disbursement records(exception error): {str(e)}"
        )
        raise HTTPException(
            status_code=400, detail=f"Failed to get activity disbursement records {str(e)}"
        )

@router.get("/last_contribution_date/{activity_id}", status_code=status.HTTP_200_OK)
async def get_the_last_contribution_date(
    activity_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity_is_active()
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        cycle_number = chama_activity.current_activity_cycle()
        # get the last contribution date for the activity
        last_contribution_date = db.query(models.LastContributionDate.last_contribution_date).filter(
            models.LastContributionDate.activity_id == activity_id,
            models.LastContributionDate.cycle_number == cycle_number,
        ).scalar()

        if not last_contribution_date:
            raise HTTPException(
                status_code=404, detail="Last contribution date not found"
            )


        return {
            "last_contribution_date": last_contribution_date.strftime("%Y-%m-%d"),
        }
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Failed to get the last contribution date(http error): {http_exc}"
        )
        raise http_exc
    except Exception as e:
        management_error_logger.error(
            f"Failed to get the last contribution date(exception error): {str(e)}"
        )
        raise HTTPException(
            status_code=400, detail=f"Failed to get the last contribution date {str(e)}"
        )


# find the sum of all paid fines so far in an activity
async def get_activity_fines_sum(activity_id: int, db: Session):
    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        first_cycle_date, last_cycle_date = None, None
        if activity.restart:
            first_cycle_date = activity.restart_date
        else:
            first_cycle_date = activity.first_contribution_date

        last_cycle_date = db.query(models.LastContributionDate.last_contribution_date).filter(
            models.LastContributionDate.activity_id == activity_id,
            models.LastContributionDate.cycle_number == chama_activity.current_activity_cycle(),
        ).scalar()

        if not last_cycle_date:
            last_cycle_date = datetime.now(nairobi_tz).date()

        fines_sum = (
            db.query(func.coalesce(func.sum(models.ActivityFine.fine), 0))
            .filter(
                and_(
                    models.ActivityFine.activity_id == activity_id,
                    models.ActivityFine.is_paid == True,
                    models.ActivityFine.fine_date >= first_cycle_date,
                    models.ActivityFine.fine_date <= last_cycle_date,
                )
            )
            .scalar()
        )

        return fines_sum
    except Exception as e:
        management_error_logger.error(f"Failed to get activity fines sum: {e}")
        raise HTTPException(status_code=400, detail="Failed to get activity fines sum")


@router.put("/admin_fees/{activity_id}", status_code=status.HTTP_200_OK)
async def update_activity_admin_fee(
    activity_id: int,
    admin_fee: schemas.AdminFeeBase,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).date()
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        activity_category = chama_activity.activity_chama_category()

        if not activity:
            raise HTTPException(
                status_code=404, detail="Activity not found or does not exist"
            )

        if activity_category != "public":
            raise HTTPException(
                status_code=403, detail="You can only update admin fee for public activities"
            )

        cycle_date = None
        if activity.restart_date:
            cycle_date = activity.restart_date
        else:
            cycle_date = activity.first_contribution_date
        

        # admin fee can only be updated before the cycle date
        if cycle_date.date() <= today:
            raise HTTPException(
                status_code=403, detail="Admin fee can only be updated before the cycle date"
            )

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You are not the manager of this activity"
            )

        # TODO: later check if there are already users who have joined the activity and update the admin_fee column of the association table
        # update the admin fee for the activity
        activity.admin_fee = admin_fee.admin_fee

        db.commit()

        return {
            "status": "success",
            "message": "Activity admin fee updated successfully",
        }
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Failed to update activity admin fee(http error): {http_exc}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Failed to update activity admin fee(exception error): {str(exc)}"
        )
        raise HTTPException(
            status_code=400, detail=f"Failed to update activity admin fee"
        )