from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from sqlalchemy import func, desc, and_

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

    if not investment_account_balance:
        raise HTTPException(status_code=404, detail="Getting investment balance failed")
    return investment_account_balance


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
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=400, detail="calculating daily interests failed"
        )


# interest earned on a certain investment by a certain chama
# when we move interest to principal, we should reset the interest, monthly
