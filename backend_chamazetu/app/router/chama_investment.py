from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from sqlalchemy import func, desc, and_
from typing import Union, List

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/investments/chamas", tags=["chama_investment"])


# invest
@router.post("/mmf", status_code=status.HTTP_201_CREATED)
async def make_an_investment(
    invest_data: schemas.InvestBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):

    try:
        print("============investing in mmfs==========")
        invest_dict = invest_data.dict()
        invest_dict["current_int_rate"] = get_current_investment_rate(
            invest_dict["investment_type"], db
        )
        invest_dict["transaction_date"] = datetime.now(timezone.utc)
        del invest_dict["investment_type"]
        print(invest_dict)

        investment_deposit = models.MMF(**invest_dict)
        db.add(investment_deposit)
        db.commit()
        db.refresh(investment_deposit)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="investment deposit failed")


def get_current_investment_rate(
    investment_type: str, db: Session = Depends(database.get_db)
):
    try:
        print("========gettingthe investment rate===========")
        investment_type = investment_type.upper()
        investment_object = (
            db.query(models.Available_Investment)
            .filter(models.Available_Investment.investment_type == investment_type)
            .first()
        )
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="could not retrieve current investment rate"
        )
    print("==========invst rate============")
    print(investment_object.investment_rate)
    return investment_object.investment_rate


# get investment details


# update the investments performance table
@router.put("/update_investment_account", status_code=status.HTTP_200_OK)
async def update_investment_account(
    account_update: schemas.UpdateInvestmentAccountBase = Body(...),
    db: Session = Depends(database.get_db),
):

    try:
        print("=========updating perfro===============")
        update_dict = account_update.dict()
        print(update_dict["investment_type"])
        chama_id = update_dict["chama_id"]
        new_amount = update_dict["amount_invested"]
        update_type = update_dict["transaction_type"]
        investment_type = update_dict["investment_type"]
        investment_name = f"chamazetu_{investment_type}"

        performance = (
            db.query(models.Investment_Performance)
            .filter(models.Investment_Performance.chama_id == chama_id)
            .filter(models.Investment_Performance.investment_type == investment_type)
            .first()
        )
        if not performance and update_type == "deposit":
            performance = models.Investment_Performance(
                chama_id=chama_id,
                amount_invested=new_amount,
                investment_type=investment_type,
                interest_earned=0.0,
                investment_name=investment_name,
                investment_start_date=datetime.now(timezone.utc),
            )
            db.add(performance)
            db.commit()
            db.refresh(performance)
        elif performance and update_type == "deposit":
            amount_invested = performance.amount_invested + new_amount
            performance.amount_invested = amount_invested
            db.commit()
            db.refresh(performance)
        elif performance and update_type == "withdraw":
            amount_invested = performance.amount_invested - new_amount
            performance.amount_invested = amount_invested
            db.commit()
            db.refresh(performance)
        else:
            raise HTTPException(
                status_code=400, detail="you have no investment to withdraw from"
            )
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="updating investment account failed"
        )


# check investment balance account for a chama
@router.get(
    "/account_balance/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.InvestmentPerformanceResp,
)
async def get_investment_account_balance(
    chama_id: int,
    db: Session = Depends(database.get_db),
):

    investment_account_balance = (
        db.query(models.Investment_Performance)
        .filter(models.Investment_Performance.chama_id == chama_id)
        .first()
    )

    interest_rate = get_current_investment_rate("MMF", db)

    if not investment_account_balance:
        raise HTTPException(status_code=404, detail="Getting investment balance failed")

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


# retrieve recent investment activity
@router.get(
    "/recent_activity/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_investments_recent_activity(
    chama_id: int,
    db: Session = Depends(database.get_db),
):

    recent_invst_activity = (
        db.query(models.MMF)
        .filter(models.MMF.chama_id == chama_id)
        .order_by(desc(models.MMF.transaction_date))
        .limit(5)
        .all()
    )

    if not recent_invst_activity:
        raise HTTPException(
            status_code=404, detail="could not fetch recent investment activity"
        )

    return recent_invst_activity


# calculating daily mmf interests
@router.put("/calculate_daily_mmf_interests", status_code=status.HTTP_200_OK)
def calculate_daily_mmf_interests(
    db: Session = Depends(database.get_db),
):

    try:
        print("============calculating daily interests==========")
        investments = db.query(models.Investment_Performance).filter(
            models.Investment_Performance.investment_type == "mmf"
        )

        for investment in investments:
            interest_rate = get_current_investment_rate(
                (investment.investment_type).upper(), db
            )
            interest_earned = investment.amount_invested * (interest_rate / 100) / 360
            investment.daily_interest = interest_earned
            investment.weekly_interest += interest_earned
            investment.monthly_interest += interest_earned
            investment.total_interest_earned += interest_earned
            db.commit()
            db.refresh(investment)

            # add this daily interest record to the daily interest table
            daily_interest = models.Daily_Interest(
                chama_id=investment.chama_id,
                interest_earned=interest_earned,
                date_earned=datetime.now(timezone.utc),
            )
            db.add(daily_interest)
            db.commit()
            db.refresh(daily_interest)
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=400, detail="calculating daily interests failed"
        )


# when we move interest to principal, we should reset the interest, monthly
# and weekly interest to zero
@router.put(
    "/reset_and_move_weekly_mmf_interest_to_principal", status_code=status.HTTP_200_OK
)
async def reset_and_move_weekly_interest_to_principal(
    db: Session = Depends(database.get_db),
):

    try:
        print(
            "============resetting and moving weekly interests to principal=========="
        )
        investments = db.query(models.Investment_Performance).filter(
            models.Investment_Performance.investment_type == "mmf"
        )

        for investment in investments:
            investment.amount_invested += investment.weekly_interest
            investment.weekly_interest = 0.0
            db.commit()
            db.refresh(investment)
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=400, detail="resetting and moving weekly interests failed"
        )


# reset the monthly interest to zero
@router.put("/reset_monthly_mmf_interest", status_code=status.HTTP_200_OK)
async def reset_monthly_interest(
    db: Session = Depends(database.get_db),
):

    try:
        print("============resetting monthly interests==========")
        investments = db.query(models.Investment_Performance).filter(
            models.Investment_Performance.investment_type == "mmf"
        )

        for investment in investments:
            # record this monthly interest to the monthly interest table
            monthly_interest = models.Monthly_Interest(
                chama_id=investment.chama_id,
                interest_earned=investment.monthly_interest,
                month=datetime.now(timezone.utc).month,
                year=datetime.now(timezone.utc).year,
                total_amount_invested=investment.amount_invested,
            )
            db.add(monthly_interest)
            db.commit()
            db.refresh(monthly_interest)

            investment.monthly_interest = 0.0
            db.commit()
            db.refresh(investment)
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=400, detail="resetting monthly interests failed"
        )


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
    current_user: Union[models.Manager, models.Member] = Depends(
        oauth2.get_current_user
    ),
):

    try:
        limit = limit.dict()["limit"]
        print("============getting daily interests==========")
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
    current_user: Union[models.Manager, models.Member] = Depends(
        oauth2.get_current_user
    ),
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
