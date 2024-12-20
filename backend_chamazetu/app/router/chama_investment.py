from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone
from sqlalchemy import func, desc, and_
from sqlalchemy.exc import SQLAlchemyError
from typing import Union, List
from fastapi.responses import JSONResponse
from zoneinfo import ZoneInfo
import logging
import math

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/investments/chamas", tags=["chama_investment"])

nairobi_tz = ZoneInfo("Africa/Nairobi")

investment_info_logger = logging.getLogger("investments_info")
investment_error_logger = logging.getLogger("investments_error")


# retrieve details on the inhouse mmf
@router.get("/in-house_mmf", status_code=status.HTTP_200_OK)
async def inhouse_mmf_data(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        print("====inhouse mmf data==========")
        inhousemmf = (
            db.query(models.Available_Investment)
            .filter(models.Available_Investment.investment_type == "mmf")
            .first()
        )

        if not inhousemmf:
            raise HTTPException(status_code=404, detail="inhouse mmf data not found")

        del inhousemmf.__dict__["investment_return"]
        print("====inhouse mmf data==========")
        print(inhousemmf.__dict__)
        return inhousemmf.__dict__
    except Exception as e:
        raise HTTPException(status_code=400, detail="inhouse mmf data not retrieva")


# retrieve available investments
@router.get(
    "/available_investments",
    status_code=status.HTTP_200_OK,
)
async def get_available_investments(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        print("=========getting available investments============")
        available_invst = db.query(models.Available_Investment).all()

        available_investments = []

        if not available_invst:
            raise HTTPException(status_code=404, detail="no available investments")
        for investment in available_invst:
            del investment.__dict__["investment_return"]
            available_investments.append(investment.__dict__)

        return available_investments
    except Exception as e:
        raise HTTPException(status_code=400, detail="retrieval of invsts failed")


# all mmf investments
@router.post("/mmf", status_code=status.HTTP_201_CREATED)
async def make_an_investment(
    invest_data: schemas.InvestBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        invest_dict = invest_data.dict()
        invest_dict["current_int_rate"] = get_current_investment_rate(
            invest_dict["investment_type"], db
        )
        invest_dict["transaction_date"] = datetime.now(nairobi_tz).replace(tzinfo=None)
        del invest_dict["investment_type"]

        investment_deposit = models.MMF(**invest_dict)
        db.add(investment_deposit)
        db.commit()
        db.refresh(investment_deposit)
    except Exception as e:
        investment_error_logger.error(f"investment deposit failed {e}")
        print(e)
        raise HTTPException(status_code=400, detail="investment deposit failed")


def get_current_investment_rate(
    investment_type: str, db: Session = Depends(database.get_db)
):
    try:
        investment_type = investment_type.lower()
        investment_object = (
            db.query(models.Available_Investment)
            .filter(models.Available_Investment.investment_type == investment_type)
            .first()
        )
    except Exception as e:
        investment_error_logger.error(f"could not retrieve current investment rate {e}")
        raise HTTPException(status_code=400, detail=str(e))
    return investment_object.investment_rate


# get investment details


# update the investments performance table
@router.put("/update_investment_account", status_code=status.HTTP_200_OK)
async def update_investment_account(
    account_update: schemas.UpdateInvestmentAccountBase = Body(...),
    db: Session = Depends(database.get_db),
):

    update_dict = account_update.dict()
    chama_id = update_dict["chama_id"]
    new_amount = update_dict["amount_invested"]
    update_type = update_dict["transaction_type"]
    investment_type = update_dict["investment_type"]
    investment_name = f"chamazetu_{investment_type.lower()}"

    """
    Using with db.begin(): ensures that all database operations within the block are treated as a
    single transaction. If any operation fails, the entire transaction is rolled back.
    """
    try:
        with db.begin():
            performance = (
                db.query(models.Investment_Performance)
                .filter(models.Investment_Performance.chama_id == chama_id)
                .filter(
                    models.Investment_Performance.investment_type == investment_type
                )
                .first()
            )
            if not performance and update_type == "deposit":
                performance = models.Investment_Performance(
                    chama_id=chama_id,
                    amount_invested=new_amount,
                    investment_type=investment_type,
                    total_interest_earned=0.0,
                    daily_interest=0.0,
                    weekly_interest=0.0,
                    monthly_interest=0.0,
                    investment_name=investment_name,
                    investment_start_date=datetime.now(nairobi_tz).replace(tzinfo=None),
                )
                db.add(performance)
            elif performance and update_type == "deposit":
                performance.amount_invested += new_amount
            elif performance and update_type == "withdraw":
                if performance.amount_invested < new_amount:
                    raise HTTPException(
                        status_code=400, detail="insufficient funds to withdraw"
                    )
                performance.amount_invested -= new_amount
            else:
                raise HTTPException(
                    status_code=400, detail="you have no investment to withdraw from"
                )
            db.commit()
            db.refresh(performance)
    except SQLAlchemyError as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "investment account updated successfully"}


# check investment balance account for a chama
@router.get(
    "/account_balance/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.InvestmentPerformanceResp,
)
async def get_investment_account_balance(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        investment_account_balance = (
            db.query(models.Investment_Performance)
            .filter(models.Investment_Performance.chama_id == chama_id)
            .first()
        )

        interest_rate = get_current_investment_rate("mmf", db)

        if not investment_account_balance:
            raise HTTPException(
                status_code=404, detail="Getting investment balance failed"
            )

        investment_performance_dict = investment_account_balance.__dict__
        investment_performance_dict["investment_rate"] = "{:.2f}".format(interest_rate)
        investment_performance_dict["daily_interest"] = "{:.2f}".format(
            investment_performance_dict["daily_interest"]
        )
        investment_performance_dict["weekly_interest"] = "{:.2f}".format(
            investment_performance_dict["weekly_interest"]
        )
        investment_performance_dict["monthly_interest"] = "{:.2f}".format(
            investment_performance_dict["monthly_interest"]
        )
        investment_performance_dict["total_interest_earned"] = "{:.2f}".format(
            investment_performance_dict["total_interest_earned"]
        )
        return schemas.InvestmentPerformanceResp(**investment_performance_dict)
    except Exception as e:
        investment_error_logger.error(f"getting investment balance failed {e}")
        raise HTTPException(status_code=400, detail="Getting investment balance failed")


# retrieve recent investment activity and withdrawals
@router.get(
    "/recent_activity/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_investments_recent_activity(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        recent_invst_activity = (
            db.query(models.MMF)
            .filter(models.MMF.chama_id == chama_id)
            .order_by(desc(models.MMF.transaction_date))
            .limit(3)
            .all()
        )

        recent_withdrawal_activity = (
            db.query(models.ChamaMMFWithdrawal)
            .filter(models.ChamaMMFWithdrawal.chama_id == chama_id)
            .filter(models.ChamaMMFWithdrawal.withdrawal_completed == True)
            .order_by(desc(models.ChamaMMFWithdrawal.withdrawal_date))
            .limit(3)
            .all()
        )

        if not recent_invst_activity:
            recent_invst_activity = []

        if not recent_withdrawal_activity:
            recent_withdrawal_activity = []

        return {
            "investment_activity": recent_invst_activity,
            "mmf_withdrawal_activity": recent_withdrawal_activity,
        }

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="could not fetch recent investment activity"
        )

    if not recent_invst_activity:
        raise HTTPException(
            status_code=404, detail="could not fetch recent investment activity"
        )

    if not recent_withdrawal_activity:
        raise HTTPException(
            status_code=404, detail="could not fetch recent withdrawal activity"
        )

    return recent_invst_activity


def truncate(number, decimals=0):
    factor = 10**decimals
    return math.trunc(number * factor) / factor


# calculating daily mmf interests
@router.put("/calculate_daily_mmf_interests", status_code=status.HTTP_200_OK)
def calculate_daily_mmf_interests(
    db: Session = Depends(database.get_db),
):

    try:
        investments = db.query(models.Investment_Performance).filter(
            models.Investment_Performance.investment_type == "mmf"
        )

        inhouse_mmf_returns = (
            db.query(models.Available_Investment)
            .filter(models.Available_Investment.investment_type == "mmf")
            .filter(models.Available_Investment.investment_name == "chamazetu_mmf")
            .first()
        )

        interest_rate = get_current_investment_rate("mmf", db)
        if inhouse_mmf_returns:
            for investment in investments:
                interest_earned = truncate(
                    (investment.amount_invested * (interest_rate / 100) / 360), 2
                )
                investment.daily_interest = interest_earned
                investment.weekly_interest += interest_earned
                investment.monthly_interest += interest_earned
                investment.total_interest_earned += interest_earned
                db.add(investment)
                db.commit()
                db.refresh(investment)

                # add all interests earned to the available investments table that shows how much has been made by that investment.
                inhouse_mmf_returns.investment_return += interest_earned
                db.add(inhouse_mmf_returns)
                db.commit()
                db.refresh(inhouse_mmf_returns)

                # add this daily interest record to the daily interest table
                daily_interest = models.Daily_Interest(
                    chama_id=investment.chama_id,
                    interest_earned=interest_earned,
                    date_earned=datetime.now(nairobi_tz).replace(tzinfo=None),
                )
                db.add(daily_interest)
                db.commit()
                db.refresh(daily_interest)
    except Exception as e:
        db.rollback()
        investment_error_logger.error(f"calculating daily interests failed {e}")
        raise HTTPException(status_code=400, detail=str(e))


# when we move interest to principal, we should reset the interest, monthly
# and weekly interest to zero
@router.put(
    "/reset_and_move_weekly_mmf_interest_to_principal", status_code=status.HTTP_200_OK
)
async def reset_and_move_weekly_interest_to_principal(
    db: Session = Depends(database.get_db),
):

    try:
        investments = db.query(models.Investment_Performance).filter(
            models.Investment_Performance.investment_type == "mmf"
        )

        for investment in investments:
            investment_info_logger.info(
                f"old amount invested {investment.amount_invested}"
            )
            investment.amount_invested += investment.weekly_interest
            investment.amount_invested = "{:.2f}".format(investment.amount_invested)
            investment.weekly_interest = 0.0
            db.commit()
            db.refresh(investment)
            investment_info_logger.info(
                f"new amount invested {investment.amount_invested}"
            )
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail=str(e))


# reset the monthly interest to zero
@router.put("/reset_monthly_mmf_interest", status_code=status.HTTP_200_OK)
async def reset_monthly_interest(
    db: Session = Depends(database.get_db),
):

    try:
        investments = (
            db.query(models.Investment_Performance)
            .filter(models.Investment_Performance.investment_type == "mmf")
            .all()
        )

        current_month = datetime.now(nairobi_tz).month
        current_year = datetime.now(nairobi_tz).year

        monthly_interests = []
        for investment in investments:
            # record this monthly interest to the monthly interest table
            monthly_interest = models.Monthly_Interest(
                chama_id=investment.chama_id,
                interest_earned=investment.monthly_interest,
                month=current_month,
                year=current_year,
                total_amount_invested=investment.amount_invested,
            )
            monthly_interests.append(monthly_interest)

        with db.begin():
            db.bulk_save_objects(monthly_interests)
            db.commit()

            # update all investments in bulk
            for investment in investments:
                db.add(investment)
            db.commit()

        return {"message": "monthly interest reset successful"}
    except SQLAlchemyError as e:
        db.rollback()
        investment_error_logger.error(f"resetting monthly interest failed {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        investment_error_logger.error(f"resetting monthly interest failed {e}")
        raise HTTPException(status_code=400, detail=str(e))


# get daily interests for the last specified days
# default is 30 days
@router.get(
    "/daily_interests/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.DailyInterestResp],
)
async def get_daily_interests(
    chama_id: int,
    limit: schemas.Limit = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        limit = limit.dict()["limit"]
        daily_interests = (
            db.query(models.Daily_Interest)
            .filter(models.Daily_Interest.chama_id == chama_id)
            .order_by(desc(models.Daily_Interest.id))
            .limit(limit)
            .all()
        )

        if not daily_interests:
            raise HTTPException(
                status_code=404, detail="could not fetch daily interests"
            )

        return [
            schemas.DailyInterestResp.from_orm(interest) for interest in daily_interests
        ]
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="getting daily interests failed")


# get monthly interests for the last specified months
# default is 3 months
@router.get(
    "/monthly_interests/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.MonthlyInterestResp],
)
async def get_monthly_interests(
    chama_id: int,
    limit: schemas.Limit = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        limit = limit.dict()["limit"]
        print("============getting monthly interests==========")
        monthly_interests = (
            db.query(models.Monthly_Interest)
            .filter(models.Monthly_Interest.chama_id == chama_id)
            .order_by(desc(models.Monthly_Interest.id))
            .limit(limit)
            .all()
        )

        if not monthly_interests:
            raise HTTPException(
                status_code=404, detail="could not fetch monthly interests"
            )

        return [
            schemas.MonthlyInterestResp.from_orm(interest)
            for interest in monthly_interests
        ]
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="getting monthly interests failed")


# retrieve minimum investment amount from available investments for a certain investment type
@router.get(
    "/minimum_investment/{investment_type}",
    status_code=status.HTTP_200_OK,
)
async def get_minimum_investment_amount(
    investment_type: str,
    db: Session = Depends(database.get_db),
):

    try:
        print("============getting minimum investment amount==========")
        investment_type = investment_type.lower()
        minimum_investment = (
            db.query(models.Available_Investment)
            .filter(models.Available_Investment.investment_type == investment_type)
            .first()
        )

        if not minimum_investment:
            raise HTTPException(
                status_code=404, detail="could not fetch minimum investment amount"
            )

        return {
            "minimum_investment": minimum_investment.min_invest_amount,
            "minimum_withdrawal": minimum_investment.min_withdrawal_amount,
        }
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="getting minimum investment amount failed"
        )


# retrieve investment period from available investments for a certain investment type
@router.get(
    "/investment_period/{investment_type}",
    status_code=status.HTTP_200_OK,
)
async def get_investment_period(
    investment_type: str,
    db: Session = Depends(database.get_db),
):

    try:
        print("============getting investment period==========")
        investment_type = investment_type.lower()
        investment_period = (
            db.query(models.Available_Investment)
            .filter(models.Available_Investment.investment_type == investment_type)
            .first()
        )

        if not investment_period:
            raise HTTPException(
                status_code=404, detail="could not fetch investment period"
            )

        return {
            "investment_period": investment_period.investment_period,
            "investment_period_unit": investment_period.investment_period_unit,
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="getting investment period failed")


# retrieve the last withdrawl date for a chama
@router.get(
    "/last_withdrawal_date/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_last_withdrawal_date(
    chama_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        print("============getting last withdrawal date==========")
        # previous withdrawal date from the chamammfwithdrawal table
        latest_withdrawal = (
            db.query(models.ChamaMMFWithdrawal)
            .filter(models.ChamaMMFWithdrawal.chama_id == chama_id)
            .filter(models.ChamaMMFWithdrawal.withdrawal_completed == True)
            .order_by(desc(models.ChamaMMFWithdrawal.withdrawal_date))
            .first()
        )

        if not latest_withdrawal:
            return {"status_code": 200, "message": "no withdrawal have been made yet"}

        return {
            "last_withdrawal_date": latest_withdrawal.withdrawal_date,
        }
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500, detail="getting last withdrawal date failed"
        )


# add withdrawal request to chama withdrawal table
@router.post("/withdrawal_requests", status_code=status.HTTP_201_CREATED)
async def make_a_withdrawal_request(
    withdraw_data: schemas.WithdrawBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        print("============withdrawing from mmfs==========")
        withdraw_dict = withdraw_data.dict()
        withdraw_dict["withdrawal_date"] = datetime.now(nairobi_tz).replace(tzinfo=None)
        withdraw_dict["withdrawal_completed"] = False
        withdraw_dict["withdrawal_status"] = "PENDING"

        print("======withdraw_dict========")
        print(withdraw_dict)

        withdrawal = models.ChamaMMFWithdrawal(**withdraw_dict)
        db.add(withdrawal)
        db.commit()
        db.refresh(withdrawal)
        return {"message": "withdrawal request successful"}
    except Exception as e:
        db.rollback()
        print("============withdrawal failed==========")
        print(e)
        raise HTTPException(status_code=400, detail="withdrawal failed")


# in an acid compliant way, we will look at all pending withdrawals and fulfill them
# by updating the withdrawal status to completed and withdrawal completed to true and also set the fulfillment date
@router.put("/fulfill_withdrawal_requests", status_code=status.HTTP_200_OK)
async def fulfill_withdrawals(
    db: Session = Depends(database.get_db),
):

    try:
        print("============fulfilling withdrawals==========")
        pending_withdrawals = (
            db.query(models.ChamaMMFWithdrawal)
            .filter(models.ChamaMMFWithdrawal.withdrawal_status == "PENDING")
            .with_for_update()  # lock the the selected rows for update and ensure that no other transaction can modify them
            .all()
        )

        # when the withdrawals are fulfilled, we neded to update the invst performance table with new amount_invested and update the chama_accounts table with the new account_balance

        # invest performance table
        for withdrawal in pending_withdrawals:
            # update the investment performance table
            investment_performance = (
                db.query(models.Investment_Performance)
                .filter(
                    and_(
                        models.Investment_Performance.chama_id == withdrawal.chama_id,
                        models.Investment_Performance.investment_type == "mmf",
                    )
                )
                .first()
            )

            if not investment_performance:
                raise HTTPException(
                    status_code=404, detail="could not find investment performance"
                )

            investment_performance.amount_invested -= withdrawal.amount

            # update the chama accounts table
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == withdrawal.chama_id)
                .first()
            )

            if not chama_account:
                raise HTTPException(
                    status_code=404, detail="could not find chama account"
                )

            chama_account.account_balance += withdrawal.amount

            # update the withdrawal table

            withdrawal.withdrawal_status = "COMPLETED"
            withdrawal.withdrawal_completed = True
            withdrawal.fulfilled_date = datetime.now(nairobi_tz).replace(tzinfo=None)

            # stage all the chnages
            db.add(investment_performance)
            db.add(chama_account)
            db.add(withdrawal)

        db.commit()  # commit all the changes as an atomic transaction
        return JSONResponse(
            status_code=200, content={"message": "fulfilling withdrawals successful"}
        )
    except Exception as e:
        db.rollback()
        print("============fulfilling withdrawals failed==========")
        print(e)
        raise HTTPException(status_code=400, detail="fulfilling withdrawals failed")
    finally:
        db.close()
        print("============fulfilling withdrawals completed==========")
