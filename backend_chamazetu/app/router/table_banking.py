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

from .date_functions import (
    calculate_custom_interval,
    calculate_monthly_interval,
    calculate_daily_interval,
    calculate_weekly_interval,
    calculate_monthly_same_day_interval,
)

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/table_banking", tags=["table_banking"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")

# set/updae the interest rate of a table banking activity
@router.put("/interest_rate/{activity_id}", status_code=status.HTTP_200_OK)
async def set_update_interest_rate(
    activity_id: int,
    interest_rate: schemas.TableBankingRateBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)


        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to update interest rate for this activity",
            )

        if interest_rate.interest_rate < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interest rate cannot be less than 5",
            )

        if interest_rate.interest_rate > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interest rate cannot be greater than 100",
            )

        # from the loan management table, retrieve the current cycle number
        cycle_number = db.query(func.max(models.TableBankingLoanManagement.cycle_number)).filter(
            models.TableBankingLoanManagement.activity_id == activity_id
        ).scalar()

        # retrieve current rate if any
        current_rate = db.query(models.TableBankingLoanSettings).filter(
            models.TableBankingLoanSettings.activity_id == activity_id
        ).first()

        if not current_rate:
            new_rate = insert(models.TableBankingLoanSettings).values(
                activity_id=activity_id,
                interest_rate=interest_rate.interest_rate,
                grace_period=0,
                updated_at=today,
                cycle_number=1,
            )
            db.execute(new_rate)
        else:
            # prevent update if the rate is the same or today is less than 30 days from the last update
            if current_rate.interest_rate == interest_rate.interest_rate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Interest rate is the same as the current rate",
                )

            current_rate.interest_rate = interest_rate.interest_rate
            current_rate.updated_at = today
            current_rate.cycle_number = cycle_number

        db.commit()

        return {"message": "Interest rate updated successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while updating interest rate for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while updating interest rate for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while updating interest rate for activity_id: {activity_id}",
        )

# set/update the await_approvalstatus from TableBankingLoanSettings
@router.put("/await_approval/{activity_id}", status_code=status.HTTP_200_OK)
async def set_update_await_approval(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to update await_approval for this activity",
            )

        # retrieve current rate if any
        current_settings = db.query(models.TableBankingLoanSettings).filter(
            models.TableBankingLoanSettings.activity_id == activity_id
        ).first()

        if not current_settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Please set the interest rate first",
            )

        # prevent update if today is less than 30 days from the last update
        current_settings.await_approval = not current_settings.await_approval

        current_settings.updated_at = today

        db.commit()

        return {"message": "Await approval status updated successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while updating await_approval for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while updating await_approval for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while updating await_approval for activity_id: {activity_id}",
        )

# TODO: set/update the grace period from TableBankingLoanSettings


# get the soft looan data for a table banking activity
@router.get("/soft_loans/manager/{activity_id}", status_code=status.HTTP_200_OK)
async def get_soft_loans_data(
    activity_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        interest_rate = db.query(models.TableBankingLoanSettings.interest_rate).filter(
            models.TableBankingLoanSettings.activity_id == activity_id
        ).scalar()

        if not interest_rate:
            return {"message": "Interest rate not set"}

        cycle_number = db.query(func.max(models.TableBankingLoanManagement.cycle_number)).filter(
            models.TableBankingLoanManagement.activity_id == activity_id
        ).scalar()

        dividend = db.query(models.TableBankingDividend).filter(
            models.TableBankingDividend.activity_id == activity_id,
            models.TableBankingDividend.cycle_number == cycle_number,
        ).first()

        loans_management = db.query(models.TableBankingLoanManagement).filter(
            models.TableBankingLoanManagement.activity_id == activity_id,
            models.TableBankingLoanManagement.cycle_number == cycle_number,
        ).first()

        account_balance = db.query(models.Activity_Account.account_balance).filter(
            models.Activity_Account.activity_id == activity_id
        ).scalar()

        return {
            "interest_rate": interest_rate,
            "unpaid_dividend": dividend.unpaid_dividends if dividend else 0.0,
            "paid_dividends": dividend.paid_dividends if dividend else 0.0,
            "total_loans_taken": loans_management.total_loans_taken if loans_management else 0.0,
            "unpaid_loans": loans_management.unpaid_loans if loans_management else 0.0,
            "paid_loans": loans_management.paid_loans if loans_management else 0.0,
            "account_balance": account_balance if account_balance else 0.0,
        }
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while fetching soft loans data for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        management_error_logger.error(
            f"Error occurred while fetching soft loans data for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while fetching soft loans data for activity_id: {activity_id}",
        )

# get soft loans dat for member of a table banking activity
@router.get("/soft_loans/members/{activity_id}", status_code=status.HTTP_200_OK)
async def get_soft_loan_data(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        user_in_activity = (
            db.query(models.activity_user_association)
            .filter(and_(models.activity_user_association.c.activity_id == activity_id, models.activity_user_association.c.user_id == current_user.id))
            .first()
        )
        
        if not user_in_activity:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this activity",
            )

        cycle_number = db.query(func.max(models.TableBankingLoanManagement.cycle_number)).filter(
            models.TableBankingLoanManagement.activity_id == activity_id
        ).scalar()

        interest_rate = db.query(models.TableBankingLoanSettings.interest_rate).filter(
            models.TableBankingLoanSettings.activity_id == activity_id,
            models.TableBankingLoanSettings.cycle_number == cycle_number,
        ).scalar()

        # get the member's soft loan data
        requested_loans = db.query(models.TableBankingRequestedLoans).filter(
            models.TableBankingRequestedLoans.activity_id == activity_id,
            models.TableBankingRequestedLoans.loan_cleared == False,
        ).all()

        # get the sum of the requested loans
        my_loan_balance = 0.0
        my_loans = []
        other_loans = []

        if requested_loans:
            my_loan_balance = sum([loan.total_required for loan in requested_loans if loan.user_id == current_user.id and loan.loan_approved])

            my_loans = [
                {
                    "user_name": loan.user_name,
                    "requested_amount": loan.requested_amount,
                    "standing_balance": loan.standing_balance,
                    "expected_interest": loan.expected_interest,
                    "total_required": loan.total_required,
                    "total_repaid": loan.total_repaid,
                    "missed_payments": loan.missed_payments,
                    "expected_repayment_date": loan.expected_repayment_date.strftime("%Y-%B-%d"),
                    "loan_cleared": loan.loan_cleared,
                    "requested_on": loan.request_date.strftime("%Y-%B-%d"),
                    "cycle_number": loan.cycle_number,
                    "action": "Approved" if loan.loan_approved else "Pending",
                }
                for loan in requested_loans
                if loan.user_id == current_user.id
            ]

            other_loans = [
                {
                    "user_name": loan.user_name,
                    "requested_amount": loan.requested_amount,
                    "standing_balance": loan.standing_balance,
                    "expected_interest": loan.expected_interest,
                    "total_required": loan.total_required,
                    "total_repaid": loan.total_repaid,
                    "missed_payments": loan.missed_payments,
                    "expected_repayment_date": loan.expected_repayment_date.strftime("%Y-%B-%d"),
                    "loan_cleared": loan.loan_cleared,
                    "requested_on": loan.request_date.strftime("%Y-%B-%d"),
                    "cycle_number": loan.cycle_number,
                    "action": "Approved" if loan.loan_approved else "Pending",
                }
                for loan in requested_loans
                if loan.user_id != current_user.id
            ]

        # this activity account balance
        account_balance = db.query(models.Activity_Account.account_balance).filter(
            models.Activity_Account.activity_id == activity_id
        ).scalar()

        return {
            "chama_id": activity.chama_id,
            "rate": interest_rate,
            "my_loan_balance": my_loan_balance,
            "my_loans": my_loans,
            "other_loans": other_loans,
            "account_balance": account_balance if account_balance else 0.0,
        }
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while fetching soft loans data for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        management_error_logger.error(
            f"Error occurred while fetching soft loans data for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while fetching soft loans data for activity_id: {activity_id}",
        )

#get loan settings as manager
@router.get("/loan_settings/{activity_id}", status_code=status.HTTP_200_OK)
async def get_loan_settings(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to view loan settings for this activity",
            )

        cycle_number = db.query(func.max(models.TableBankingLoanManagement.cycle_number)).filter(
            models.TableBankingLoanManagement.activity_id == activity_id
        ).scalar()

        loan_settings = db.query(models.TableBankingLoanSettings).filter(
            models.TableBankingLoanSettings.activity_id == activity_id,
            models.TableBankingLoanSettings.cycle_number == cycle_number,
        ).first()

        if not loan_settings:
            return {"loan_settings": None}

        return {"loan_settings": loan_settings}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while fetching loan settings for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        management_error_logger.error(
            f"Error occurred while fetching loan settings for activity_id: {activity_id} - {exc}")


# get eligbility loans for all.
# we will use thre tables, the users, activity_user_association, and the table_banking_loan_eligibility
# the output will be a lis of all usernames, loan_limit(if none = 0) and their eligibility status
# the table_banking_loan_eligibility only carries records of users who have a set loan limit or eligible is set to false
@router.get("/loan_eligibility_data/{activity_id}", status_code=status.HTTP_200_OK)
async def get_eligibility_loans(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        # get all users in the activity
        users = db.query(models.User).join(
            models.activity_user_association,
            models.User.id == models.activity_user_association.c.user_id,
        ).filter(models.activity_user_association.c.activity_id == activity_id).all()

        # get the loan eligibility for each user
        eligibility = db.query(models.TableBankingLoanEligibility).filter(
            models.TableBankingLoanEligibility.activity_id == activity_id
        ).all()

        # get the loan settings
        loan_settings = db.query(models.TableBankingLoanSettings).filter(
            models.TableBankingLoanSettings.activity_id == activity_id
        ).first()
        
        eligibility_data = []
        for user in users:
            user_eligibility = next((el for el in eligibility if el.user_id == user.id), None)
            if user_eligibility:
                eligibility_data.append(
                    {
                        "user_id": user.id,
                        "user_name": f"{user.first_name} {user.last_name}",
                        "loan_limit": "Not set" if not user_eligibility.loan_limit else user_eligibility.loan_limit,
                        "eligible": user_eligibility.eligible,
                    }
                )
            else:
                eligibility_data.append(
                    {
                        "user_id": user.id,
                        "user_name": f"{user.first_name} {user.last_name}",
                        "loan_limit": "Not set",
                        "eligible": True,
                    }
                )

        return {"eligibility_data": eligibility_data, "chama_id": activity.chama_id}

    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while fetching loan settings for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        management_error_logger.error(
            f"Error occurred while fetching loan settings for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while fetching loan settings for activity_id: {activity_id}",
        )


# restrict a user from requesting a loan
@router.put("/restrict_user_loan_access/{activity_id}/{user_id}", status_code=status.HTTP_200_OK)
async def restric_loan_access(
    activity_id: int,
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to restrict user access for this activity",
            )

        user_in_activity = db.query(models.User).join(
            models.activity_user_association,
            models.User.id == models.activity_user_association.c.user_id,
        ).filter(
            and_(models.activity_user_association.c.activity_id == activity_id, models.activity_user_association.c.user_id == user_id)
        ).first()

        if not user_in_activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this activity",
            )

        # get the loan eligibility for the user
        user_eligibility = db.query(models.TableBankingLoanEligibility).filter(
            models.TableBankingLoanEligibility.activity_id == activity_id,
            models.TableBankingLoanEligibility.user_id == user_id,
        ).first()

        if user_eligibility and user_eligibility.eligible == False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User loan access is already restricted",
            )

        if not user_eligibility:
            new_restrict = insert(models.TableBankingLoanEligibility).values(
                user_name = f"{user_in_activity.first_name} {user_in_activity.last_name}",
                activity_id=activity_id,
                user_id=user_id,
                eligible=False,
                updated_at=datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0),
            )
            db.execute(new_restrict)

        else:
            user_eligibility.eligible = False

        db.commit()

        return {"message": "User access restricted successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while restricting user access for activity_id: {activity_id} - {http_exc.detail}")
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while restricting user access for activity_id: {activity_id} - {exc}")


# allow a user to request a loan
@router.put("/allow_loan_access/{activity_id}/{user_id}", status_code=status.HTTP_200_OK)
async def allow_loan_access(
    activity_id: int,
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to allow user access for this activity",
            )

        user_in_activity = db.query(models.User).join(
            models.activity_user_association,
            models.User.id == models.activity_user_association.c.user_id,
        ).filter(
            and_(models.activity_user_association.c.activity_id == activity_id, models.activity_user_association.c.user_id == user_id)
        ).first()

        if not user_in_activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this activity",
            )

        # get the loan eligibility for the user
        user_eligibility = db.query(models.TableBankingLoanEligibility).filter(
            models.TableBankingLoanEligibility.activity_id == activity_id,
            models.TableBankingLoanEligibility.user_id == user_id,
        ).first()

        if user_eligibility and user_eligibility.eligible == True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User loan access is already allowed",
            )

        if not user_eligibility:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User loan access is not restricted",
            )
        else:
            #TODO: if there is a record, delete it
            db.delete(user_eligibility)

        db.commit()
        return {"message": "User access allowed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while allowing user access for activity_id: {activity_id} - {http_exc.detail}")

        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while allowing user access for activity_id: {activity_id} - {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while allowing user access for activity_id: {activity_id}",
        )

# has the user cleared their contribution for the day
async def get_member_contribution_so_far(user_id: int, activity_id: int, db):
    try:
        contribution_dates = (
            db.query(models.ActivityContributionDate)
            .filter(models.ActivityContributionDate.activity_id == activity_id)
            .first()
        )
        prev_contribution_date = contribution_dates.previous_contribution_date.date()
        next_contribution_date = contribution_dates.next_contribution_date.date()

        # rewrite the above query to sum the amount using coalesce
        total_contributions = (
            db.query(func.coalesce(func.sum(models.ActivityTransaction.amount), 0))
            .filter(
                and_(
                    models.ActivityTransaction.user_id == user_id,
                    models.ActivityTransaction.activity_id == activity_id,
                    models.ActivityTransaction.transaction_completed == True,
                    models.ActivityTransaction.transaction_type == "contribution",
                    models.ActivityTransaction.is_reversed == False,
                    func.date(models.ActivityTransaction.transaction_date)
                    > prev_contribution_date,
                    func.date(models.ActivityTransaction.transaction_date)
                    <= next_contribution_date,
                )
            )
            .scalar()
        )

        return total_contributions
    except Exception as e:
        raise HTTPException(
            status_code=400, detail="Failed to get members contribution so far"
        )

@router.get("/soft_loans/eligibility/{activity_id}", status_code=status.HTTP_200_OK)
async def check_eligibility(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        user_id = current_user.id
        activity = (
            db.query(models.Activity)
            .filter(models.Activity.id == activity_id)
            .first()
        )

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        user_in_activity = db.query(models.activity_user_association).filter(
            and_(models.activity_user_association.c.activity_id == activity_id, models.activity_user_association.c.user_id == user_id)
        ).first()

        if not user_in_activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this activity",
            )

        # get the loan eligibility for the user
        # later we will check users loan limit
        restricted = db.query(models.TableBankingLoanEligibility).filter(
            models.TableBankingLoanEligibility.activity_id == activity_id,
            models.TableBankingLoanEligibility.user_id == user_id,
            models.TableBankingLoanEligibility.eligible == False,
        ).first()

        if restricted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are not allowed to request a loan, please contact the manager",
            )

        # check if the user has an active loan
        active_loan = db.query(models.TableBankingRequestedLoans).filter(
            models.TableBankingRequestedLoans.activity_id == activity_id,
            models.TableBankingRequestedLoans.user_id == user_id,
            models.TableBankingRequestedLoans.loan_approved == True,
            models.TableBankingRequestedLoans.loan_cleared == False,
        ).first()

        if active_loan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have an active loan, please clear it first",
            )

        # check if the user has any fines
        fines = db.query(models.ActivityFine).filter(
            models.ActivityFine.activity_id == activity_id,
            models.ActivityFine.user_id == user_id,
            models.ActivityFine.is_paid == False,
        ).all()

        if fines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have fines, please clear them first",
            )

        # check if the next contribution date is today
        today = datetime.now(nairobi_tz).date()
        next_contribution_date = db.query(models.ActivityContributionDate.next_contribution_date).filter(
            models.ActivityContributionDate.activity_id == activity_id
        ).scalar()

        if not next_contribution_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contribution dates not set, please contact the manager",
            )

        if next_contribution_date.date() == today:
            # check if the user has contributed the required amount
            total_contributions = await get_member_contribution_so_far(user_id, activity_id, db)
            expected_contribution = user_in_activity.shares * user_in_activity.share_value
            if total_contributions < expected_contribution:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You have not contributed the required amount for today. Please contribute first",
                )

            # if today is not contribution day, the users loan will have to await approval

        return {
            "is_eligible": True,
            "contribution_day_is_today": next_contribution_date.date() == today,
        }
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while checking eligibility for activity_id:http_exc: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        management_error_logger.error(
            f"Error occurred while checking eligibility for activity_id: exc: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while checking your eligibility for this activity",
        )

# request a soft loan
@router.post("/request_soft_loan/members/{activity_id}", status_code=status.HTTP_201_CREATED)
async def request_soft_loan(
    activity_id: int,
    loan_request: schemas.TableBankingRequestLoan,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        user_id = current_user.id
        contribution_day_is_today = loan_request.contribution_day_is_today
        requested_amount = loan_request.requested_amount

        with db.begin_nested():
            activity = (
                db.query(models.Activity)
                .filter(models.Activity.id == activity_id)
                .first()
            )

            if not activity:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

            user_in_activity = db.query(models.activity_user_association).filter(
                and_(models.activity_user_association.c.activity_id == activity_id, models.activity_user_association.c.user_id == user_id)
            ).first()

            if not user_in_activity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User is not a member of this activity",
                )

            # retrieve the loan settings
            loan_settings = db.query(models.TableBankingLoanSettings).filter(
                models.TableBankingLoanSettings.activity_id == activity_id
            ).first()

            if not loan_settings:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please set the interest rate first",
                )

            # determine if approval is needed
            await_approval = contribution_day_is_today and loan_settings.await_approval
            expected_repayment_date = await calculate_repayment_date(today, activity, contribution_day_is_today)

            cycle_number = db.query(func.max(models.TableBankingLoanManagement.cycle_number)).filter(
                models.TableBankingLoanManagement.activity_id == activity_id
            ).scalar()
            expected_interest = round((requested_amount * loan_settings.interest_rate) / 100, 2)

            loan_request = models.TableBankingRequestedLoans(
                activity_id=activity_id,
                user_name=f"{current_user.first_name} {current_user.last_name}",
                user_id=user_id,
                requested_amount=requested_amount,
                standing_balance=requested_amount,
                missed_payments=0,
                expected_interest=expected_interest,
                total_required=requested_amount + expected_interest,
                total_repaid=0.0,
                request_date=today,
                expected_repayment_date=expected_repayment_date,
                cycle_number=cycle_number,
                loan_approved=not await_approval,
                loan_cleared=False,
            )
            db.add(loan_request)

            # if awaiting approval, do not update balances
            if not await_approval:
                activity_account = db.query(models.Activity_Account).filter(
                    models.Activity_Account.activity_id == activity_id
                ).with_for_update().first()
                if not activity_account or activity_account.account_balance < requested_amount:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient activity account balance")

                activity_account.account_balance -= requested_amount

                # chama account balance
                chama_account = db.query(models.Chama_Account).filter(
                    models.Chama_Account.chama_id == activity.chama_id
                ).with_for_update().first()

                if not chama_account or chama_account.account_balance < requested_amount:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insufficient chama account balance")

                chama_account.account_balance -= requested_amount

                # loan management table
                loans_table = db.query(models.TableBankingLoanManagement).filter(
                    models.TableBankingLoanManagement.activity_id == activity_id
                ).with_for_update().first()

                loans_table.total_loans_taken += requested_amount
                loans_table.unpaid_loans += requested_amount

                # update user wallet with the loan amount
                user_wallet = db.query(models.User).filter(models.User.id == user_id).with_for_update().first()
                if not user_wallet:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User wallet not found",
                    )

                user_wallet.wallet_balance += requested_amount

            db.commit()

        return {"message": "Loan request successful"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while requesting soft loan for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while requesting soft loan for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while requesting soft loan for activity_id: {activity_id}",
        )

async def calculate_repayment_date(today, activity, contribution_day_is_today):
    if contribution_day_is_today:
        if activity.frequency == "daily":
            return calculate_daily_interval(today.date())
        elif activity.frequency == "weekly":
            return calculate_weekly_interval(today.date())
        elif activity.frequency == "monthly" and activity.interval in ["first", "second", "third", "fourth", "last"]:
            return calculate_monthly_interval(today.date(), activity.interval, activity.contribution_day)
        elif activity.frequency == "monthly" and activity.interval == "monthly":
            return calculate_monthly_same_day_interval(today.date(), int(activity.contribution_day))
        elif activity.frequency == "interval" and activity.interval == "custom":
            return calculate_custom_interval(today.date(), int(activity.contribution_day))
    else:
        if activity.frequency == "daily":
            return calculate_daily_interval(today.date())
        elif activity.frequency == "weekly":
            return calculate_weekly_interval(today.date())
        elif activity.frequency == "monthly":
            return today.date() + timedelta(days=30)
        elif activity.frequency == "interval" and activity.interval == "custom":
            return today.date() + timedelta(days=(int(activity.contribution_day)))