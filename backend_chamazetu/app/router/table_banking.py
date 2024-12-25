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
from .activities import get_active_activity_by_id, get_active_user_in_activity, get_activity_cycle_number, get_activity_fines_sum, chamaActivity
from .members import contributions_total

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

        loans = db.query(models.TableBankingRequestedLoans).filter(
            models.TableBankingRequestedLoans.activity_id == activity_id,
            models.TableBankingRequestedLoans.rejected == False,
            models.TableBankingRequestedLoans.loan_cleared == False,
        ).all()

        unapproved_loans, approved_loans = [], []

        if loans:
            unapproved_loans = [
                {
                    "loan_id": loan.id,
                    "user_name": loan.user_name,
                    "requested_amount": loan.requested_amount,
                    "expected_interest": loan.expected_interest,
                    "requested_on": loan.request_date.strftime("%Y-%B-%d"),
                    "cycle_number": loan.cycle_number,
                }
                for loan in loans
                if not loan.loan_approved
            ]

            approved_loans = [
                {
                    "loan_id": loan.id,
                    "user_name": loan.user_name,
                    "requested_amount": loan.requested_amount,
                    "standing_balance": loan.standing_balance,
                    "expected_interest": loan.expected_interest,
                    "total_required": loan.total_required,
                    "total_repaid": loan.total_repaid,
                    "missed_payments": loan.missed_payments,
                    "expected_repayment_date": loan.expected_repayment_date.strftime("%Y-%B-%d"),
                    "requested_on": loan.request_date.strftime("%Y-%B-%d"),
                    "cycle_number": loan.cycle_number,
                }
                for loan in loans
                if loan.loan_approved
            ]

        return {
            "interest_rate": interest_rate,
            "unpaid_dividend": dividend.unpaid_dividends if dividend else 0.0,
            "paid_dividends": dividend.paid_dividends if dividend else 0.0,
            "total_loans_taken": loans_management.total_loans_taken if loans_management else 0.0,
            "unpaid_loans": loans_management.unpaid_loans + loans_management.unpaid_interest if loans_management else 0.0,
            "paid_loans": loans_management.paid_loans if loans_management else 0.0,
            "account_balance": account_balance if account_balance else 0.0,
            "unapproved_loans": unapproved_loans,
            "approved_loans": approved_loans,
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
            models.TableBankingRequestedLoans.rejected == False,
        ).all()

        dividend = db.query(models.TableBankingDividend).filter(
            models.TableBankingDividend.activity_id == activity_id,
            models.TableBankingDividend.cycle_number == cycle_number,
        ).first()

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
            "unpaid_dividend": dividend.unpaid_dividends if dividend else 0.0,
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
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        cycle_number = chama_activity.current_activity_cycle()

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
            models.TableBankingLoanSettings.activity_id == activity_id,
            models.TableBankingLoanSettings.cycle_number == cycle_number,
        ).first()
        
        eligibility_data = []
        for user in users:
            user_eligibility = next((el for el in eligibility if el.user_id == user.id), None)
            if user_eligibility:
                eligibility_data.append(
                    {
                        "user_id": user.id,
                        "user_name": f"{user.first_name} {user.last_name}",
                        "loan_limit": 0 if not user_eligibility.loan_limit else user_eligibility.loan_limit,
                        "eligible": user_eligibility.eligible,
                    }
                )
            else:
                eligibility_data.append(
                    {
                        "user_id": user.id,
                        "user_name": f"{user.first_name} {user.last_name}",
                        "loan_limit": 0,
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

            cycle_number = await get_activity_cycle_number(activity_id, db)

            # retrieve the loan settings
            loan_settings = db.query(models.TableBankingLoanSettings).filter(
                models.TableBankingLoanSettings.activity_id == activity_id,
                models.TableBankingLoanSettings.cycle_number == cycle_number,
            ).first()

            if not loan_settings:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please ask the manager to set the interest rate first",
                )

            # determine if approval is needed
            await_approval = contribution_day_is_today and loan_settings.await_approval
            expected_repayment_date = await calculate_repayment_date(today, activity, contribution_day_is_today)

            cycle_number = db.query(func.max(models.TableBankingLoanManagement.cycle_number)).filter(
                models.TableBankingLoanManagement.activity_id == activity_id
            ).scalar()
            expected_interest = calculate_interest(requested_amount, loan_settings.interest_rate)

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
                loan_approved_date=today if not await_approval else None,
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
                    models.TableBankingLoanManagement.activity_id == activity_id,
                    models.TableBankingLoanManagement.cycle_number == cycle_number,
                ).with_for_update().first()

                loans_table.total_loans_taken += requested_amount
                loans_table.unpaid_loans += requested_amount
                loans_table.unpaid_interest += expected_interest

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


# paying a soft loan - prioriity is to pay the interest first
@router.post("/soft_loans/repayment/members/{activity_id}", status_code=status.HTTP_201_CREATED)
async def pay_soft_loan(
    activity_id: int,
    loan_payment: schemas.TableBankingPayLoan = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        if current_user.wallet_balance < loan_payment.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance",
            )

        activity = await get_active_activity_by_id(activity_id, db)
        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        user_in_activity = await get_active_user_in_activity(activity_id, current_user.id, db)

        if not user_in_activity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this activity",
            )

        cycle_number = await get_activity_cycle_number(activity_id, db)

        with db.begin_nested():
            requested_loans = db.query(models.TableBankingRequestedLoans).filter(
                models.TableBankingRequestedLoans.activity_id == activity_id,
                models.TableBankingRequestedLoans.user_id == current_user.id,
                models.TableBankingRequestedLoans.loan_approved == True,
                models.TableBankingRequestedLoans.loan_cleared == False,
            ).order_by(models.TableBankingRequestedLoans.request_date).with_for_update().all()

            if not requested_loans:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No outstanding loans found",
                )

            loan_management = db.query(models.TableBankingLoanManagement).filter(
                models.TableBankingLoanManagement.activity_id == activity_id,
                models.TableBankingLoanManagement.cycle_number == cycle_number,
            ).with_for_update().first()

            dividends = db.query(models.TableBankingDividend).filter(
                models.TableBankingDividend.activity_id == activity_id,
                models.TableBankingDividend.cycle_number == cycle_number,
            ).with_for_update().first()

            if not dividends or not loan_management:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Loan management or dividends not found",
                )

            paying_amount = loan_payment.amount
            total_repaid = 0.0
            total_interest_paid = 0.0
            total_principal_paid = 0.0

            for loan in requested_loans:
                loan_payment_details = process_loan_payment(loan, paying_amount)
                paying_amount -= loan_payment_details["total_repaid"]
                total_interest_paid += loan_payment_details["interest_paid"]
                total_principal_paid += loan_payment_details["principal_paid"]
                total_repaid += loan_payment_details["total_repaid"]

                if loan_payment_details["loan_cleared"]:
                    loan.loan_cleared = True
                    loan.repaid_date = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)

                # update the loan management table
            loan_management.paid_loans += total_principal_paid
            loan_management.paid_interest += total_interest_paid
            loan_management.unpaid_loans -= total_principal_paid
            loan_management.unpaid_interest -= total_interest_paid

            # update dividends with the interest paid (unpaid dividends)
            dividends.unpaid_dividends += total_interest_paid

            # update the activity account balance
            activity_account = db.query(models.Activity_Account).filter(
                models.Activity_Account.activity_id == activity_id
            ).with_for_update().first()

            if not activity_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Activity account not found",
                )
            
            activity_account.account_balance += total_repaid

            # update the chama account balance
            chama_account = db.query(models.Chama_Account).filter(
                models.Chama_Account.chama_id == activity.chama_id
            ).with_for_update().first()

            if not chama_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chama account not found",
                )

            chama_account.account_balance += total_repaid

            # update the user wallet
            user_record = db.query(models.User).filter(models.User.id == current_user.id).with_for_update().first()
            user_record.wallet_balance -= total_repaid

            db.commit()

        return {"message": "Loan payment successful"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while paying soft loan for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while paying soft loan for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while paying soft loan for this activity",
        )


def process_loan_payment(loan, paying_amount):
    """Helper function to process payment for a single loan."""
    interest_paid = 0.0
    principal_paid = 0.0
    total_repaid = 0.0

    if loan.expected_interest > 0:
        pay_interest = min(loan.expected_interest, paying_amount)
        interest_paid += pay_interest
        paying_amount -= pay_interest
        total_repaid += pay_interest
        loan.expected_interest -= pay_interest

    if paying_amount > 0 and loan.standing_balance > 0:
        pay_principal = min(loan.standing_balance, paying_amount)
        principal_paid += pay_principal
        paying_amount -= pay_principal
        total_repaid += pay_principal
        loan.standing_balance -= pay_principal

    loan.total_repaid += total_repaid
    loan.total_required -= total_repaid

    return {
        "interest_paid": interest_paid,
        "principal_paid": principal_paid,
        "total_repaid": total_repaid,
        "loan_cleared": loan.standing_balance == 0 and loan.expected_interest == 0,
    }


# approve loans as manager
@router.put("/approve_loan/{activity_id}/{loan_id}", status_code=status.HTTP_200_OK)
async def approve_loan(
    activity_id: int,
    loan_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = await get_active_activity_by_id(activity_id, db)

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to approve loans for this activity",
            )

        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        with db.begin_nested():
            loan = db.query(models.TableBankingRequestedLoans).filter(
                models.TableBankingRequestedLoans.id == loan_id,
                models.TableBankingRequestedLoans.activity_id == activity_id,
                models.TableBankingRequestedLoans.loan_approved == False,
                models.TableBankingRequestedLoans.loan_cleared == False,
            ).first()

            if not loan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Loan not found",
                )

            cycle_number = await get_activity_cycle_number(activity_id, db)

            # loan management table
            loan_management = db.query(models.TableBankingLoanManagement).filter(
                models.TableBankingLoanManagement.activity_id == activity_id,
                models.TableBankingLoanManagement.cycle_number == cycle_number,
            ).with_for_update().first()

            if not loan_management:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Loan management not found",
                )


            loan_management.unpaid_loans += loan.requested_amount
            loan_management.unpaid_interest += loan.expected_interest
            loan_management.total_loans_taken += loan.requested_amount

            loan.loan_approved = True
            loan.loan_approved_date = today
            # updating the expected_repayment_date to the an interval of this activity from the current date(today)
            loan.expected_repayment_date = await calculate_repayment_date(today, activity, True)


            # update the activity account balance
            activity_account = db.query(models.Activity_Account).filter(
                models.Activity_Account.activity_id == activity_id
            ).with_for_update().first()

            if not activity_account or activity_account.account_balance < loan.requested_amount:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Insufficient activity account balance",
                )

            activity_account.account_balance -= loan.requested_amount

            # update the chama account balance
            chama_account = db.query(models.Chama_Account).filter(
                models.Chama_Account.chama_id == activity.chama_id
            ).with_for_update().first()

            if not chama_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chama account not found",
                )

            chama_account.account_balance -= loan.requested_amount

            # update the user wallet
            user_record = db.query(models.User).filter(models.User.id == loan.user_id).with_for_update().first()
            if not user_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User wallet not found",
                )

            user_record.wallet_balance += loan.requested_amount

            db.commit()

        return {"message": "Loan approved successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while approving loan for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while approving loan for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while approving loan for activity_id: {activity_id}",
        )


# reject loans as manager
@router.put("/decline_loan/{activity_id}/{loan_id}", status_code=status.HTTP_200_OK)
async def reject_loan(
    activity_id: int,
    loan_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        activity = await get_active_activity_by_id(activity_id, db)

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        if activity.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to reject loans for this activity",
            )


        loan = db.query(models.TableBankingRequestedLoans).filter(
            models.TableBankingRequestedLoans.id == loan_id,
            models.TableBankingRequestedLoans.activity_id == activity_id,
            models.TableBankingRequestedLoans.loan_approved == False,
            models.TableBankingRequestedLoans.loan_cleared == False,
        ).first()

        if not loan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Loan not found",
            )

        loan.loan_approved = False
        loan.rejected = True

        db.commit()

        return {"message": "Loan rejected successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while rejecting loan for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while rejecting loan for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while rejecting loan for activity_id: {activity_id}",
        )


# retrieving all approved loans requested from a certain date to another
@router.get("/loan_history/{activity_id}", status_code=status.HTTP_200_OK)
async def retrieve_loan_history(
    activity_id: int,
    dates: schemas.TableBankingLoanHistory,
    db: Session = Depends(database.get_db),
):
    try:
        activity = await get_active_activity_by_id(activity_id, db)

        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        cycle_number = await get_activity_cycle_number(activity_id, db)

        from_date = datetime.strptime(dates.from_date, "%Y-%m-%d")
        to_date = datetime.strptime(dates.to_date, "%Y-%m-%d")

        # order by request date in descending order
        requested_loans = db.query(models.TableBankingRequestedLoans).filter(
            models.TableBankingRequestedLoans.activity_id == activity_id,
            models.TableBankingRequestedLoans.cycle_number == cycle_number,
            func.date(models.TableBankingRequestedLoans.request_date) >= from_date.date(),
            func.date(models.TableBankingRequestedLoans.request_date) <= to_date.date(),
        ).order_by(models.TableBankingRequestedLoans.request_date.desc()).all()

        loans = [
            {
                "user_name": loan.user_name,
                "requested_amount": loan.requested_amount,
                "standing_balance": loan.standing_balance,
                "missed_payments": loan.missed_payments,
                "expected_interest": loan.expected_interest,
                "total_required": loan.total_required,
                "total_repaid": loan.total_repaid,
                "missed_payments": loan.missed_payments,
                "request_date": loan.request_date.strftime("%Y-%m-%d %H:%M:%S"),
                "expected_repayment_date": loan.expected_repayment_date.strftime("%Y-%m-%d"),
                "repaid_date": loan.repaid_date.strftime("%Y-%m-%d %H:%M:%S") if loan.repaid_date else "",
                "loan_approved": "approved" if loan.loan_approved else "rejected",
                "loan_approved_date": loan.loan_approved_date.strftime("%Y-%m-%d %H:%M:%S") if loan.loan_approved_date else "",
                "loan_cleared": "cleared" if loan.loan_cleared else "not cleared",
            }
            for loan in requested_loans
        ]

        loans_data = db.query(models.TableBankingLoanManagement).filter(
            models.TableBankingLoanManagement.activity_id == activity_id,
            models.TableBankingLoanManagement.cycle_number == cycle_number,
        ).first()


        return {"loans": loans, "unpaid_loans": loans_data.unpaid_loans, "paid_loans": loans_data.paid_loans, "paid_interest": loans_data.paid_interest, "unpaid_interest": loans_data.unpaid_interest}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while retrieving loan history for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        management_error_logger.error(
            f"Error occurred while retrieving loan history for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while retrieving loan history for this activity",
        )


# updating the loan records if they are past the expected repayment date, loan cleared=false and approved=true - all loans for active activities and users
# we will update two tables, requested_loans and loan_management.
# we will update the standing balance as the total required amount and calculate new interest on that standing balance
# we will update the missed_payments + 1, we will also update the total required amount and the expected_repayment_date
# for loan management, we will update total_loans_taken, unpaid_loans, unpaid_interest
# total_loans_taken = total_loans_taken + previous expected_interest
# unpaid_loans = unpaid_loans + previous expected_interest
# unpaid_interest = unpaid_interest + new expected_interest

@router.put("/update_table_banking_loans", status_code=status.HTTP_200_OK)
async def update_table_banking_loans(
    db: Session = Depends(database.get_db),
):
    try:
        today = datetime.now(nairobi_tz).date()
        with db.begin():
            # get all activities
            activities = db.query(models.Activity).filter(
                and_(
                    models.Activity.is_active == True,
                    models.Activity.activity_type == "table-banking",
                )
            ).all()

            activity_ids = [activity.id for activity in activities]
            print("===activity ids:\n", activity_ids)

            overdue_loans = (
                db.query(models.TableBankingRequestedLoans).filter(
                models.TableBankingRequestedLoans.activity_id.in_(activity_ids),
                models.TableBankingRequestedLoans.loan_approved == True,
                models.TableBankingRequestedLoans.loan_cleared == False,
                func.date(models.TableBankingRequestedLoans.expected_repayment_date) < today,
                )
                .with_for_update()
                .all()
            )
            print("===overdue loans:\n", overdue_loans)

            if not overdue_loans:
                return {"message": "No overdue loans found"}

            # organize loans by activity for easier managemnet updates
            loans_by_activity = {}
            for loan in overdue_loans:
                if loan.activity_id not in loans_by_activity:
                    loans_by_activity[loan.activity_id] = []
                loans_by_activity[loan.activity_id].append(loan)

            for activity in activities:
                cycle_number = await get_activity_cycle_number(activity.id, db)
                interest_rate = db.query(models.TableBankingLoanSettings.interest_rate).filter(
                    models.TableBankingLoanSettings.activity_id == activity.id
                ).scalar()

                if activity.id not in loans_by_activity:
                    # skip if there are no overdue loans for this activity
                    continue

                # loan management record for this activity
                loan_management = db.query(models.TableBankingLoanManagement).filter(
                    models.TableBankingLoanManagement.activity_id == activity.id,
                    models.TableBankingLoanManagement.cycle_number == cycle_number,
                ).with_for_update().first()

                if not loan_management:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Loan management not found",
                    )

                # aggregate values for bulk updating loan management
                total_previous_interest = 0.0
                total_new_interest = 0.0

                for loan in loans_by_activity[activity.id]:
                    # update the loan record
                    previous_expected_interest = loan.expected_interest

                    loan.standing_balance = loan.total_required
                    loan.expected_interest = calculate_interest(loan.standing_balance, interest_rate)
                    loan.missed_payments += 1
                    loan.total_required = loan.standing_balance + loan.expected_interest
                    loan.expected_repayment_date = await calculate_repayment_date(loan.expected_repayment_date, activity, True)


                    total_previous_interest += previous_expected_interest
                    total_new_interest += loan.expected_interest - previous_expected_interest

                # update the loan management record
                loan_management.total_loans_taken += total_previous_interest
                loan_management.unpaid_loans += total_previous_interest
                loan_management.unpaid_interest += total_new_interest

            db.commit()

        return {"message": "Loan records updated successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while updating loan records - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while updating loan records - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while updating loan records",
        )

def calculate_interest(balance, interest_rate):
    return round((balance * interest_rate) / 100)


# dividend records - we will retrive all users in this activity their ames, number of shares
# sum of active loans for each user, sum of active fines and their dividend so far
#this are records only
@router.get("/dividend_disbursement_records/{activity_id}", status_code=status.HTTP_200_OK)
async def dividend_disbursement_records(
    activity_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

        cycle_number = chama_activity.current_activity_cycle()
        if not cycle_number:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No cycle number found",
            )

        paid_fines = chama_activity.current_cycle_paid_fines()

        # get all the users in this activity - active users
        active_users = (
            db.query(
                models.activity_user_association,
                models.User.first_name,
                models.User.last_name,
                )
                .join(models.User, models.User.id == models.activity_user_association.c.user_id)
                .filter(
                    models.activity_user_association.c.activity_id == activity_id,
                    models.activity_user_association.c.user_is_active == True,
                    ).all()
                    )

        user_ids = [user.user_id for user in active_users]

        # get the dividend records for this cycle
        dividends = db.query(models.TableBankingDividend).filter(
            models.TableBankingDividend.activity_id == activity_id,
            models.TableBankingDividend.cycle_number == cycle_number,
        ).first()

        if not dividends:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dividends not found",
            )

        # get all the active loans for this cycle in this activity
        active_loans_users = db.query(models.TableBankingRequestedLoans).filter(
            models.TableBankingRequestedLoans.activity_id == activity_id,
            models.TableBankingRequestedLoans.loan_approved == True,
            models.TableBankingRequestedLoans.loan_cleared == False,
            models.TableBankingRequestedLoans.cycle_number == cycle_number,
            models.TableBankingRequestedLoans.user_id.in_(user_ids),
        ).all()


        # get all the active fines for this cycle in this activity
        active_fines_users = db.query(models.ActivityFine).filter(
            models.ActivityFine.activity_id == activity_id,
            models.ActivityFine.is_paid == False,
            models.ActivityFine.user_id.in_(user_ids),
        ).all()

        active_loans_fines_users_ids = [loan.user_id for loan in active_loans_users] + [fine.user_id for fine in active_fines_users]

        activity_account = db.query(models.Activity_Account.account_balance).filter(
            models.Activity_Account.activity_id == activity_id
        ).scalar()

        num_of_shares = sum([user.shares for user in active_users])
        dividend_per_share = int(dividends.unpaid_dividends / num_of_shares)
        
        # Create a dictionary with user contributions data indexed by user_id for quicker access
        user_contributions_dict = {
            user.user_id: {
                "contributions": result["contributions"],
                "late_contributions": result["late_contributions"],
                "paid_fines": result["paid_fines"],
                "unpaid_fines": result["unpaid_fines"],
            }
            for user in active_users
            for result in [await contributions_total(activity_id, user.user_id, db)]
        }

        # Generate dividend records with direct access to user contributions data
        dividend_records = [
            {
                "user_name": f"{user.first_name} {user.last_name}",
                "shares": user.shares,
                "active_loans": sum(loan.standing_balance for loan in active_loans_users if loan.user_id == user.user_id) + sum(loan.expected_interest for loan in active_loans_users if loan.user_id == user.user_id),
                "active_fines": sum(fine.expected_repayment for fine in active_fines_users if fine.user_id == user.user_id),
                "dividend_earned": user.shares * dividend_per_share,
                "eligible": "yes" if user.user_id not in active_loans_fines_users_ids else "no",
                "contributions": user_contributions_dict[user.user_id]["contributions"],
                "late_contributions": user_contributions_dict[user.user_id]["late_contributions"] - user_contributions_dict[user.user_id]["paid_fines"],
                "paid_fines": user_contributions_dict[user.user_id]["paid_fines"],
                "unpaid_fines": user_contributions_dict[user.user_id]["unpaid_fines"],
                "principal": (
                    user_contributions_dict[user.user_id]["contributions"]
                    + user_contributions_dict[user.user_id]["late_contributions"]
                    - user_contributions_dict[user.user_id]["paid_fines"]
                    - user_contributions_dict[user.user_id]["unpaid_fines"]
                ),
            }
            for user in active_users
        ]

        return {
            "dividend_records": dividend_records,
            "activity_account_balance": activity_account, 
            "dividend_earned": dividends.unpaid_dividends,
            "cycle_number": cycle_number,
            "paid_fines": paid_fines,
            "activity_category": chama_activity.activity_chama_category(),
        }

    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while retrieving dividend records for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        management_error_logger.error(
            f"Error occurred while retrieving dividend records for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while retrieving dividend records for this activity",
        )


# disburse dividends only
@router.put("/disburse_dividends_only/{activity_id}", status_code=status.HTTP_200_OK)
async def disburse_dividends_only(
    activity_id: int,
    next_contribution_date: schemas.NextContributionDate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        next_contribution_date = datetime.strptime(next_contribution_date.next_contribution_date, "%Y-%m-%d")
        with db.begin_nested():
            chama_activity = chamaActivity(db, activity_id)
            activity = chama_activity.activity()
            if not activity:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

            if activity.manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not allowed to disburse dividends for this activity",
                )

            cycle_number = chama_activity.current_activity_cycle()

            # get the dividends for this cycle
            dividends = db.query(models.TableBankingDividend).filter(
                models.TableBankingDividend.activity_id == activity_id,
                models.TableBankingDividend.cycle_number == cycle_number,
            ).with_for_update().first()

            if not dividends:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dividends not found",
                )

            # get all the users in this activity
            active_users = db.query(models.activity_user_association).filter(
                models.activity_user_association.c.activity_id == activity_id,
                models.activity_user_association.c.user_is_active == True,
            ).all()
            user_ids = [user.user_id for user in active_users]

            # active loans for this cycle in this activity
            active_loans_users = db.query(models.TableBankingRequestedLoans).filter(
                models.TableBankingRequestedLoans.activity_id == activity_id,
                models.TableBankingRequestedLoans.loan_approved == True,
                models.TableBankingRequestedLoans.loan_cleared == False,
                models.TableBankingRequestedLoans.cycle_number == cycle_number,
            ).distinct().all()


            active_fines_users = db.query(models.ActivityFine).filter(
                models.ActivityFine.activity_id == activity_id,
                models.ActivityFine.is_paid == False,
            ).distinct().all()

            active_loans_fines_users_ids = [loan.user_id for loan in active_loans_users] + [fine.user_id for fine in active_fines_users]

            users_to_disburse = [user for user in active_users if user.user_id not in active_loans_fines_users_ids]

            total_amount_disbursed = 0.0
            sum_of_all_shares = sum([user.shares for user in active_users])
            dividend_per_share = dividends.unpaid_dividends / sum_of_all_shares

            disbursement_records = []
            for user in users_to_disburse:
                dividend_earned = user.shares * dividend_per_share

                user_wallet = db.query(models.User).filter(models.User.id == user.user_id).with_for_update().first()
                # add a disbursement record
                disbursement_records.append(models.TableBankingDividendDisbursement(
                    activity_id=activity_id,
                    user_id=user.user_id,
                    user_name = f"{user_wallet.first_name} {user_wallet.last_name}",
                    shares=user.shares,
                    dividend_amount=int(dividend_earned),
                    principal_amount=0.0,
                    disbursement_date=today,
                    cycle_number=cycle_number,
                ))

                total_amount_disbursed += dividend_earned
                user_wallet.wallet_balance += int(dividend_earned)

            # bulk insert
            db.bulk_save_objects(disbursement_records)

            # update the dividend table
            dividends.paid_dividends += total_amount_disbursed
            dividends.unpaid_dividends -= total_amount_disbursed

            # new entry for the next cycle
            db.add(models.TableBankingDividend(
                chama_id=activity.chama_id,
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
                unpaid_dividends=0.0,
                paid_dividends=0.0,
            ))

            db.add(models.ActivityCycle(
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
            ))

            # new entry for the next cycle in the loan management table
            db.add(models.TableBankingLoanManagement(
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
                total_loans_taken=0.0,
                unpaid_loans=0.0,
                paid_loans=0.0,
                unpaid_interest=0.0,
                paid_interest=0.0,
            ))

            # update the activity contribution date table with the next contribution date
            contribution_date = db.query(models.ActivityContributionDate).filter(
                models.ActivityContributionDate.activity_id == activity_id
            ).with_for_update().first()

            if not contribution_date:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contribution date not found",
                )

            contribution_date.next_contribution_date = next_contribution_date
            contribution_date.previous_contribution_date = today.date()

            # update the activity account balance
            activity_account = db.query(models.Activity_Account).filter(
                models.Activity_Account.activity_id == activity_id
            ).with_for_update().first()

            chama_account = db.query(models.Chama_Account).filter(
                models.Chama_Account.chama_id == activity.chama_id
            ).with_for_update().first()

            if not activity_account or not chama_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Activity account or chama account not found",
                )

            activity_account.account_balance -= total_amount_disbursed
            chama_account.account_balance -= total_amount_disbursed

            # update activity restart to true and restart date to the next contribution date
            activity.restart = True
            activity.restart_date = next_contribution_date

            db.commit()

        return {"message": "Dividends disbursed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while disbursing dividends for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while disbursing dividends for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while disbursing dividends for activity"
        )

# disburse dividends and principal
@router.put("/disburse_dividends_and_principal/{activity_id}", status_code=status.HTTP_200_OK)
async def disburse_dividends_and_principal(
    activity_id: int,
    next_contribution_date: schemas.NextContributionDate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        next_contribution_date = datetime.strptime(next_contribution_date.next_contribution_date, "%Y-%m-%d")
        with db.begin_nested():
            chama_activity = chamaActivity(db, activity_id)
            activity = chama_activity.activity()
            if not activity:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

            if activity.manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not allowed to disburse dividends for this activity",
                )

            cycle_number = chama_activity.current_activity_cycle()
            # get the dividends for this cycle
            dividends = db.query(models.TableBankingDividend).filter(
                models.TableBankingDividend.activity_id == activity_id,
                models.TableBankingDividend.cycle_number == cycle_number,
            ).with_for_update().first()

            if not dividends:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dividends not found",
                )

            # get all the users in this activity
            active_users = db.query(models.activity_user_association).filter(
                models.activity_user_association.c.activity_id == activity_id,
                models.activity_user_association.c.user_is_active == True,
            ).all()
            user_ids = [user.user_id for user in active_users]

            # active loans for this cycle in this activity
            active_loans_users = db.query(models.TableBankingRequestedLoans).filter(
                models.TableBankingRequestedLoans.activity_id == activity_id,
                models.TableBankingRequestedLoans.loan_approved == True,
                models.TableBankingRequestedLoans.loan_cleared == False,
                models.TableBankingRequestedLoans.cycle_number == cycle_number,
            ).distinct().all()


            active_fines_users = db.query(models.ActivityFine).filter(
                models.ActivityFine.activity_id == activity_id,
                models.ActivityFine.is_paid == False,
            ).distinct().all()

            active_loans_fines_users = [loan.user_id for loan in active_loans_users] + [fine.user_id for fine in active_fines_users]

            users_to_disburse = [user for user in active_users if user.user_id not in active_loans_fines_users]

            total_amount_disbursed = 0.0
            sum_of_all_shares = sum([user.shares for user in active_users])
            dividend_per_share = dividends.unpaid_dividends / sum_of_all_shares

            disbursement_records = []
            for user in users_to_disburse:
                dividend_earned = user.shares * dividend_per_share

                user_contribution = await contributions_total(activity_id, user.user_id, db)
                principal_amount = user_contribution["contributions"] + user_contribution["late_contributions"] - user_contribution["paid_fines"] - user_contribution["unpaid_fines"]

                user_wallet = db.query(models.User).filter(models.User.id == user.user_id).with_for_update().first()
                # add a disbursement record
                disbursement_records.append(models.TableBankingDividendDisbursement(
                    activity_id=activity_id,
                    user_id=user.user_id,
                    user_name = f"{user_wallet.first_name} {user_wallet.last_name}",
                    shares=user.shares,
                    dividend_amount=int(dividend_earned),
                    principal_amount=int(principal_amount),
                    disbursement_date=today,
                    cycle_number=cycle_number,
                ))

                total_amount_disbursed += dividend_earned + principal_amount
                user_wallet.wallet_balance += int(dividend_earned + principal_amount)

            # bulk insert
            db.bulk_save_objects(disbursement_records)

            # update the dividend table
            dividends.paid_dividends += total_amount_disbursed
            dividends.unpaid_dividends -= total_amount_disbursed

            # new entry for the next cycle
            db.add(models.TableBankingDividend(
                chama_id=activity.chama_id,
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
                unpaid_dividends=0.0,
                paid_dividends=0.0,
            ))

            db.add(models.ActivityCycle(
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
            ))

            # new entry for the next cycle in the loan management table
            db.add(models.TableBankingLoanManagement(
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
                total_loans_taken=0.0,
                unpaid_loans=0.0,
                paid_loans=0.0,
                unpaid_interest=0.0,
                paid_interest=0.0,
            ))

            # update the activity contribution date table with the next contribution date
            contribution_date = db.query(models.ActivityContributionDate).filter(
                models.ActivityContributionDate.activity_id == activity_id
            ).with_for_update().first()

            if not contribution_date:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contribution date not found",
                )

            contribution_date.next_contribution_date = next_contribution_date
            contribution_date.previous_contribution_date = today.date()

            # update the activity account balance
            activity_account = db.query(models.Activity_Account).filter(
                models.Activity_Account.activity_id == activity_id
            ).with_for_update().first()

            chama_account = db.query(models.Chama_Account).filter(
                models.Chama_Account.chama_id == activity.chama_id
            ).with_for_update().first()

            if not activity_account or not chama_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Activity account or chama account not found",
                )

            activity_account.account_balance -= total_amount_disbursed
            chama_account.account_balance -= total_amount_disbursed

            # update activity restart to true and restart date to the next contribution date
            activity.restart = True
            activity.restart_date = next_contribution_date

            db.commit()

        return {"message": "Dividends and principal disbursed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while disbursing dividends and principal for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while disbursing dividends and principal for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while disbursing dividends and principal for activity"
        )


# disburse dividends, principal and fines collected to the members according to their shares
@router.put("/disburse_dividends_principal_fines/{activity_id}", status_code=status.HTTP_200_OK)
async def disburse_dividends_principal_fines(
    activity_id: int,
    next_contribution_date: schemas.NextContributionDate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        today = datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0)
        next_contribution_date = datetime.strptime(next_contribution_date.next_contribution_date, "%Y-%m-%d")
        with db.begin_nested():
            chama_activity = chamaActivity(db, activity_id)
            activity = cha_activity.activity()

            if not activity:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity not found",)

            if activity.manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not allowed to disburse dividends for this activity",
                )

            cycle_number = chama_activity.current_activity_cycle()

            # get the dividends for this cycle
            dividends = db.query(models.TableBankingDividend).filter(
                models.TableBankingDividend.activity_id == activity_id,
                models.TableBankingDividend.cycle_number == cycle_number,
            ).with_for_update().first()

            if not dividends:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dividends not found",
                )

            # get all the users in this activity
            active_users = db.query(models.activity_user_association).filter(
                models.activity_user_association.c.activity_id == activity_id,
                models.activity_user_association.c.user_is_active == True,
            ).all()
            user_ids = [user.user_id for user in active_users]

            # active loans for this cycle in this activity
            active_loans_users = db.query(models.TableBankingRequestedLoans).filter(
                models.TableBankingRequestedLoans.activity_id == activity_id,
                models.TableBankingRequestedLoans.loan_approved == True,
                models.TableBankingRequestedLoans.loan_cleared == False,
                models.TableBankingRequestedLoans.cycle_number == cycle_number,
            ).distinct().all()


            active_fines_users = db.query(models.ActivityFine).filter(
                models.ActivityFine.activity_id == activity_id,
                models.ActivityFine.is_paid == False,
            ).distinct().all()

            active_loans_fines_users = [loan.user_id for loan in active_loans_users] + [fine.user_id for fine in active_fines_users]

            users_to_disburse = [user for user in active_users if user.user_id not in active_loans_fines_users]

            total_amount_disbursed = 0.0
            sum_of_paid_fines = await get_activity_fines_sum(activity_id, db)
            sum_of_all_shares = sum([user.shares for user in active_users])
            dividend_per_share = dividends.unpaid_dividends / sum_of_all_shares

            # sum of all shares of users who are not in active loans or fines (users_to_disburse)
            sum_of_eligible_shares = sum([user.shares for user in users_to_disburse])
            fine_per_eligible_share = sum_of_paid_fines / sum_of_eligible_shares

            disbursement_records = []
            for user in users_to_disburse:
                dividend_earned = user.shares * dividend_per_share
                fines_earned = user.shares * fine_per_eligible_share

                user_contribution = await contributions_total(activity_id, user.user_id, db)
                principal_amount = user_contribution["contributions"] + user_contribution["late_contributions"] - user_contribution["paid_fines"] - user_contribution["unpaid_fines"]

                user_wallet = db.query(models.User).filter(models.User.id == user.user_id).with_for_update().first()
                # add a disbursement record
                disbursement_records.append(models.TableBankingDividendDisbursement(
                    activity_id=activity_id,
                    user_id=user.user_id,
                    user_name = f"{user_wallet.first_name} {user_wallet.last_name}",
                    shares=user.shares,
                    dividend_amount=int(dividend_earned),
                    principal_amount=int(principal_amount),
                    fines_amount=int(fines_earned),
                    disbursement_date=today,
                    cycle_number=cycle_number,
                ))

                total_amount_disbursed += dividend_earned + principal_amount + fines_earned
                user_wallet.wallet_balance += int(dividend_earned + principal_amount)

            # bulk insert
            db.bulk_save_objects(disbursement_records)

            # update the dividend table
            dividends.paid_dividends += total_amount_disbursed
            dividends.unpaid_dividends -= total_amount_disbursed

            # new entry for the next cycle
            db.add(models.TableBankingDividend(
                chama_id=activity.chama_id,
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
                unpaid_dividends=0.0,
                paid_dividends=0.0,
            ))

            db.add(models.ActivityCycle(
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
            ))

            # new entry for the next cycle in the loan management table
            db.add(models.TableBankingLoanManagement(
                activity_id=activity_id,
                cycle_number=cycle_number + 1,
                total_loans_taken=0.0,
                unpaid_loans=0.0,
                paid_loans=0.0,
                unpaid_interest=0.0,
                paid_interest=0.0,
            ))

            # update the activity contribution date table with the next contribution date
            contribution_date = db.query(models.ActivityContributionDate).filter(
                models.ActivityContributionDate.activity_id == activity_id
            ).with_for_update().first()

            if not contribution_date:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contribution date not found",
                )

            contribution_date.next_contribution_date = next_contribution_date
            contribution_date.previous_contribution_date = today.date()

            # update the activity account balance
            activity_account = db.query(models.Activity_Account).filter(
                models.Activity_Account.activity_id == activity_id
            ).with_for_update().first()

            chama_account = db.query(models.Chama_Account).filter(
                models.Chama_Account.chama_id == activity.chama_id
            ).with_for_update().first()

            if not activity_account or not chama_account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Activity account or chama account not found",
                )

            activity_account.account_balance -= total_amount_disbursed
            chama_account.account_balance -= total_amount_disbursed

            # update activity restart to true and restart date to the next contribution date
            activity.restart = True
            activity.restart_date = next_contribution_date

            db.commit()

        return {"message": "Dividends and principal disbursed successfully"}
    except HTTPException as http_exc:
        management_error_logger.error(
            f"Error occurred while disbursing dividends and principal for activity_id: {activity_id} - {http_exc.detail}"
        )
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(
            f"Error occurred while disbursing dividends and principal for activity_id: {activity_id} - {exc}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred while disbursing dividends and principal for activity"
        )
