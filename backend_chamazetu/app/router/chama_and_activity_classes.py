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

router = APIRouter(prefix="/activities", tags=["activities"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")


#  CHAMA ACTIVITY CLASS
class chamaActivity:
    def __init__(self, db: Session, activity_id: int):
        self.db = db
        self.activity_id = activity_id

    def activity_is_active(self) -> bool:
        """check if an activity is active"""
        activity = self.db.query(models.Activity).filter(
            models.Activity.id == self.activity_id,
            models.Activity.is_active == True,
        ).first()

        return True if activity else False

    def activity(self) -> dict:
        """retrieve activity details"""
        activity = self.db.query(models.Activity).filter(
            models.Activity.id == self.activity_id,
            models.Activity.is_active == True,
            ).first()

        return activity

    def activity_chama_category(self) -> str:
        """is the activity part of a public or private chama"""
        chama_category = self.db.query(models.Chama.category).filter(
            models.Chama.id == self.activity().chama_id
        ).scalar()

        return chama_category

    def activity_manager(self) -> dict:
        """retrieve the manager for given activity"""
        manager_id = self.db.query(models.Activity.manager_id).filter(
            models.Activity.id == self.activity_id
        ).scalar()

        manager = self.db.query(models.User).filter(models.User.id == manager_id).first()

        return {
            "manager_id": manager.id,
            "manager_name": f"{manager.first_name} {manager.last_name}",
            "manager_email": manager.email,
        }

    def admin_fee(self) -> int:
        """retrieve the admin fee for an activity"""
        admin_fee = self.db.query(models.Activity.admin_fee).filter(
            models.Activity.id == self.activity_id
        ).scalar()

        return admin_fee or 0

    def activity_members(self) -> List[dict]:
        """retrieve all members of a given activity"""
        members = (
            self.db.query(models.User)
            .join(
                models.activity_user_association,
                models.User.id == models.activity_user_association.c.user_id,
            )
            .filter(models.activity_user_association.c.activity_id == self.activity_id)
            .all()
        )

        members_list = []
        for member in members:
            members_list.append(
                {
                    "member_id": member.id,
                    "member_name": f"{member.first_name} {member.last_name}",
                    "member_email": member.email,
                    "active": "active" if member.is_active else "inactive",
                }
            )

        return members_list

    def number_of_active_members(self) -> int:
        """count the number of active members in an activity"""
        count = (
            self.db.query(func.count(models.activity_user_association.c.user_id))
            .filter(
                models.activity_user_association.c.activity_id == self.activity_id,
                models.activity_user_association.c.user_is_active == True,
            )
            .scalar()
        )

        return count or 0

    def number_of_inactive_members(self) -> int:
        """count the number of inactive members in an activity"""
        count = (
            self.db.query(func.count(models,activity_user_association.c.user_id))
            .filter(
                models.activity_user_association.c.activity_id == self.activity_id,
                models.activity_user_association.c.user_is_active == False,
            )
            .scalar()
        )

        return count or 0

    def previous_and_upcoming_contribution_dates(self) -> dict:
        """retrieve the previous and the upcoming contribution dasy for an activity"""
        contribution_days = self.db.query(models.ActivityContributionDate).filter(
            models.ActivityContributionDate.activity_id == self.activity_id
        ).first()

        return {
            "previous_contribution_date": contribution_days.previous_contribution_date,
            "next_contribution_date": contribution_days.next_contribution_date,
        }

    def activity_creation_date(self) -> datetime:
        """retrieve an activity's creation date"""
        creation_date = self.db.query(models.Activity.creation_date).filter(
            models.Activity.id == self.activity_id
        ).scalar()

        return creation_date

    def activity_type(self) -> str:
        """retrieve the type of activity"""
        activity_type = self.db.query(models.Activity.activity_type).filter(
            models.Activity.id == self.activity_id
        ).scalar()

        return activity_type

    def current_activity_cycle(self) -> int:
        """retrieve the current cycle number for an activity"""
        cycle = self.db.query(models.ActivityCycle.cycle_number).filter(
            models.ActivityCycle.activity_id == self.activity_id
        ).scalar()

        return cycle or 0

    # we are going to retrieve the max cycle number in the rotatiom_order table specifically for merry_go_round activities
    def merry_go_round_max_cycle(self) -> int:
        """retrieve the max cycle number for a merry_go_round activity"""
        max_cycle = self.db.query(func.max(models.RotationOrder.cycle_number)).filter(
            models.RotationOrder.activity_id == self.activity_id
        ).scalar()

        return max_cycle or 0

    def activity_dates(self) -> dict:
        """creation date, first_contribution_date, last_contribution_date, restart_date"""
        dates = self.db.query(models.Activity).filter(models.Activity.id == self.activity_id).first()
        last_contribution_date = self.db.query(models.LastContributionDate).filter(
            models.LastContributionDate.activity_id == self.activity_id,
            models.LastContributionDate.cycle_number == self.current_activity_cycle(),
            ).first()

        return {
            "creation_date": dates.creation_date,
            "first_contribution_date": dates.first_contribution_date,
            "last_contribution_date": last_contribution_date,
            "restart_date": dates.restart_date,
        }

    def activity_account_balance(self) -> Float:
        """retrieve the account balance for an activity"""
        balance = self.db.query(models.Activity_Account.account_balance).filter(
            models.Activity_Account.activity_id == self.activity_id
        ).scalar()

        return balance or 0.0

    def paid_and_unpaid_dividends(self) -> dict:
        """retrieve dividend records for table banking activities"""
        # check activity type first
        if self.activity_type() == "table-banking":
            dividends = self.db.query(models.TableBankingDividend).filter(
                models.TableBankingDividend.activity_id == self.activity_id,
                models.TableBankingDividend.cycle_number == self.current_activity_cycle(),
            ).first()

            return {
                "unpaid_dividends": dividends.unpaid_dividends,
                "paid_dividends": dividends.paid_dividends,
            }
        
    def unpaid_loans_and_interest(self) -> dict:
        """retrieve the total unpaid loans for a table banking activity"""
        if self.activity_type() == "table-banking":
            unpaid = self.db.query(models.TableBankingLoanManagement).filter(
                models.TableBankingLoanManagement.activity_id == self.activity_id,
                models.TableBankingLoanManagement.cycle_number == self.current_activity_cycle(),
            ).first()

            return {
                "unpaid_loans": unpaid.unpaid_loans,
                "unpaid_interest": unpaid.unpaid_interest,
            }

    def paid_loans_and_interest(self) -> dict:
        """retrieve the total paid loans for a table banking activity"""
        if self.activity_type() == "table-banking":
            loans = self.db.query(models.TableBankingLoanManagement).filter(
                models.TableBankingLoanManagement.activity_id == self.activity_id,
                models.TableBankingLoanManagement.cycle_number == self.current_activity_cycle(),
            ).first()

            return {
                "paid_loans": loans.paid_loans,
                "paid_interest": loans.paid_interest,
            }

    def current_cycle_unpaid_fines_and_missed_amount(self) -> dict:
        """retrieve the total unpaid fines for an activity"""
        current_cycle = self.current_activity_cycle()
        unpaid_fines = self.db.query(func.coalesce(func.sum(models.ActivityFine.fine), 0)).filter(
            models.ActivityFine.activity_id == self.activity_id,
            models.ActivityFine.is_paid == False,
            models.ActivityFine.cycle_number == current_cycle,
        ).scalar()

        missed_amount = self.db.query(func.coalesce(func.sum(models.ActivityFine.missed_amount), 0)).filter(
            models.ActivityFine.activity_id == self.activity_id,
            models.ActivityFine.is_paid == False,
            models.ActivityFine.cycle_number == current_cycle,
        ).scalar()


        return {
            "unpaid_fines": unpaid_fines or 0.0,
            "missed_amount": missed_amount or 0.0,
            "total_unpaid": unpaid_fines + missed_amount,
        }

    def current_cycle_paid_fines(self) -> Float:
        """retrieve the total paid fines for an activity"""
        paid_fines = self.db.query(func.coalesce(func.sum(models.ActivityFine.fine), 0)).filter(
            models.ActivityFine.activity_id == self.activity_id,
            models.ActivityFine.is_paid == True,
            models.ActivityFine.cycle_number == self.current_activity_cycle(),
        ).scalar()

        return paid_fines or 0.0

    def fines_available_for_transfer(self) -> int:
        """we will first check if there is a fines transfer record for the current cycle
        in the ManagerFiesTransfer table. if there is, we will only sum the paid_fines whose
        paid_date is > than the transfer date and <= today. if there is no transfer record, if there is no transfer record,
        we will return the current_cycle_paid_fines
        """

        today = datetime.now(nairobi_tz).date()
        previous_transfer = self.db.query(models.ManagerFinesTransfer).filter(
            models.ManagerFinesTransfer.activity_id == self.activity_id,
            models.ManagerFinesTransfer.cycle_number == self.current_activity_cycle(),
        ).first()

        if previous_transfer:
            paid_fines = self.db.query(func.coalesce(func.sum(models.ActivityFine.fine), 0)).filter(
                models.ActivityFine.activity_id == self.activity_id,
                models.ActivityFine.is_paid == True,
                models.ActivityFine.cycle_number == self.current_activity_cycle(),
                models.ActivityFine.paid_date > previous_transfer.transfer_date,
                models.ActivityFine.paid_date <= today,
            ).scalar()
        else:
            paid_fines = self.current_cycle_paid_fines()

        return paid_fines or 0.0


    def todays_contributions(self) -> Float:
        """retrieve the total contribution for today"""
        today = datetime.now(nairobi_tz).date()
        todays_contributions = (
            self.db.query(func.coalesce(func.sum(models.ActivityTransaction.amount), 0))
            .filter(
                models.ActivityTransaction.activity_id == self.activity_id,
                models.ActivityTransaction.transaction_type == "contribution",
                models.ActivityTransaction.transaction_completed == True,
                func.date(models.ActivityTransaction.transaction_date) == today,
            )
            .scalar()
            or 0.0
        )

        return todays_contributions

class chamaManager:
    def __init__(self, db: Session, chama_id: int):
        self.db = db
        self.chama_id = chama_id

    def chama(self):
        return self.db.query(models.Chama).filter(models.Chama.id == self.chama_id).first()

    def chama_category(self):
        return self.chama().category