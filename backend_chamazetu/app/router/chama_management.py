from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import func, update, and_, table, column

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/chamas", tags=["management"])


# create chama for a logged in manager
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ChamaResp)
async def create_chama(
    chama: schemas.ChamaBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):

    print("-------backend current user\n", current_user)
    try:
        chama_dict = chama.dict()
        chama_dict["manager_id"] = current_user.id

        new_chama = models.Chama(**chama_dict)
        db.add(new_chama)
        db.commit()
        db.refresh(new_chama)

        return {"Chama": [new_chama]}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create chama")


# set contribution day for a chama during creation by checkign the start date, interval and day


# updating contribution days for chamas
@router.put("/update_contribution_days", status_code=status.HTTP_200_OK)
async def update_contribution_days(
    db: Session = Depends(database.get_db),
):
    # get chama_ids, contribution_interval, contribution_day from chamas
    chamas = db.query(models.Chama).order_by(models.Chama.id).all()
    chamas_details = {}
    for chama in chamas:
        chamas_details[chama.id] = {
            "contribution_interval": chama.contribution_interval,
            "contribution_day": chama.contribution_day,
        }

    for chama_id, details in chamas_details.items():
        contribution_interval = details["contribution_interval"]
        contribution_day = details["contribution_day"]

        upcoming_contribution_date = calculate_next_contribution_date(
            contribution_interval, contribution_day
        )
        chama_contribution_day = (
            db.query(models.ChamaContributionDay).filter_by(chama_id=chama_id).first()
        )

        if chama_contribution_day:
            # the chama_id exists - update the contribution day
            if upcoming_contribution_date > datetime.now():
                chama_contribution_day.next_contribution_date = (
                    upcoming_contribution_date
                )
                print(
                    f"Chama {chama_id} contribution day updated to {upcoming_contribution_date}"
                )
            else:
                chama_contribution_day.next_contribution_date = (
                    calculate_next_contribution_date(
                        contribution_interval, contribution_day
                    )
                )
        else:
            # the chama_id does not exist - create a new record
            new_record = models.ChamaContributionDay(
                chama_id=chama_id, next_contribution_date=upcoming_contribution_date
            )
            db.add(new_record)
            print(f"Chama {chama_id} contribution day created")

    db.commit()

    return {"message": "Contribution days updated successfully"}


# ====================================================
def calculate_next_contribution_date(contribution_interval, contribution_day):
    today = datetime.now()
    contribution_day_index = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }
    next_contribution_date = None
    if contribution_interval == "daily":
        next_contribution_date = today + timedelta(days=1)
    elif contribution_interval == "weekly":
        today_index = today.weekday()
        contribution_day_index_value = contribution_day_index[
            contribution_day.capitalize()
        ]
        days_until_contribution_day = (contribution_day_index_value - today_index) % 7
        if days_until_contribution_day == 0:
            # if today is the contribution day check if time is past the contribution time, if not, set the next contribution day to today else set it to next week
            # if today.time() < contribution_time:
            #     next_contribution_date = today
            if today.time() < datetime.strptime("12:00", "%H:%M").time():
                next_contribution_date = today
            else:
                next_contribution_date = today + timedelta(weeks=1)
        else:
            next_contribution_date = today + timedelta(days=days_until_contribution_day)

    elif contribution_interval == "monthly":
        # ensure the day is not 29, 30 or 31 for months that don't have those days
        if today.month == 2 and contribution_day > 28:
            contribution_day = 28

        if today.day <= int(contribution_day):
            # contribution day hasn't passed this month yet
            next_month = today.replace(day=int(contribution_day))
        else:
            # contribution day has passed this month
            next_month = today.replace(day=int(contribution_day))
            next_month = next_month.replace(month=next_month.month + 1)
        next_contribution_date = next_month
    return next_contribution_date


# ====================================================


# get chama by name for a logged in manager
@router.get("/", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp)
async def get_chama_by_name(
    chama_name: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    chama_name = chama_name["chama_name"]
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# get chama by id for a logged in member
@router.get("/chama", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp)
async def get_chama_by_id(
    chama_id: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chama_id = chama_id["chamaid"]
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# get chama by name for a logged in member
@router.get(
    "/chama_name", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def get_chama_by_name(
    chama_name: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chama_name = chama_name["chamaname"]
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# getting the chama for a public user - no authentication required
# TODO: the table being querries should be chama_blog/details and not chama, description should match in both
@router.get(
    "/public_chama", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def view_chama(
    chama_id: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    chama_id = chama_id["chamaid"]
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    # we will use the id to extract the manager details like profile photo
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# changing the status of a chama accepting new members or not
@router.put("/join_status", status_code=status.HTTP_200_OK)
async def change_chama_status(
    status: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    print("status", status)
    accepting_members = status["accepting_members"]
    chama_name = status["chama_name"]

    chama = db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    chama.accepting_members = accepting_members
    db.commit()
    return {"message": "Status updated successfully"}


# members can join chamas
@router.post("/join", status_code=status.HTTP_201_CREATED)
async def join_chama(
    chama_details: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chamaname = chama_details["chamaname"]
    num_of_shares = chama_details["num_of_shares"]
    member_id = current_user.id

    chama = db.query(models.Chama).filter(models.Chama.chama_name == chamaname).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")

    # Check if the current user is already a member of the chama
    if current_user in chama.members:
        raise HTTPException(
            status_code=400, detail="You are already a member of this chama"
        )

    chama.members.append(current_user)
    db.commit()
    return {"message": f"You have successfully joined {chamaname}"}


# members add the number of shares they want to have in a chama
@router.put("/update_shares", status_code=status.HTTP_200_OK)
async def add_shares(
    shares: schemas.ChamaMemberSharesBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    shares = shares.dict()
    chama_id = shares["chama_id"]
    num_of_shares = shares["num_of_shares"]
    member_id = current_user.id

    add_shares = (
        update(models.members_chamas_association)
        .where(
            and_(
                models.members_chamas_association.c.member_id == member_id,
                models.members_chamas_association.c.chama_id == chama_id,
            )
        )
        .values(num_of_shares=num_of_shares)
    )
    db.execute(add_shares)
    db.commit()
    return {"message": "Shares added successfully"}


# members can leave chamas


# members retrieving all chamas they are part of using a list of chamaids
@router.get(
    "/my_chamas", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def my_chamas(
    chamaids: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chamaids = chamaids["chamaids"]
    chamas = db.query(models.Chama).filter(models.Chama.id.in_(chamaids)).all()
    if not chamas:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": chamas}


# retrieving chama id from its name
@router.get("/chama_id/{chamaname}", status_code=status.HTTP_200_OK)
async def get_chama_id(
    chamaname: str,
    db: Session = Depends(database.get_db),
):
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chamaname).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama_id": chama.id}


# retrieving all member ids of a chama
@router.get("/members/{chama_id}", status_code=status.HTTP_200_OK)
async def get_chama_members(
    chama_id: str,
    db: Session = Depends(database.get_db),
):
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Members": [member.id for member in chama.members]}


# update accounts balance for a certain chama after a deposit transaction
@router.put(
    "/update_account",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ChamaAccountResp,
)
async def update_account_balance(
    account: schemas.ChamaAccountBase = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        account_dict = account.dict()
        chama_id = account_dict["chama_id"]
        new_amount = account_dict["amount_deposited"]
        transanction_type = account_dict["transaction_type"]

        chama_account = (
            db.query(models.Chama_Account)
            .filter(models.Chama_Account.chama_id == chama_id)
            .first()
        )
        account_balance = 0
        if not chama_account and transanction_type == "deposit":
            chama_account = models.Chama_Account(
                chama_id=chama_id, account_balance=new_amount
            )
            db.add(chama_account)
            db.commit()
            db.refresh(chama_account)
            return chama_account
        elif chama_account and transanction_type == "deposit":
            account_balance = chama_account.account_balance + new_amount
        elif chama_account and transanction_type == "withdraw":
            account_balance = chama_account.account_balance - new_amount
        else:
            raise HTTPException(
                status_code=400, detail="Failed to update account balance"
            )

        # this is a background task, might not be necessary to return the updated account balance
        chama_account.account_balance = account_balance
        db.commit()
        db.refresh(chama_account)
        return chama_account

    except Exception as e:
        print("------error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to update account balance")


# retrieve chama account balance
@router.get(
    "/account_balance/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ChamaAccountResp,
)
async def get_chama_account_balance(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    chama_account_balance = (
        db.query(models.Chama_Account)
        .filter(models.Chama_Account.chama_id == chama_id)
        .first()
    )
    if not chama_account_balance:
        raise HTTPException(status_code=404, detail="Chama account not found")
    return chama_account_balance


# retrieve all transactions to a chama done today and are deposits and sum the total amount
@router.get(
    "/today_deposits/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_today_deposit(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    today = datetime.now().date()
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.chama_id == chama_id)
        .filter(models.Transaction.transaction_type == "deposit")
        .filter(func.date(models.Transaction.date_of_transaction) == today)
        .all()
    )

    for transaction in transactions:
        print(transaction.date_of_transaction)

    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions found")
    total_amount = sum([transaction.amount for transaction in transactions])
    return {"today_deposits": total_amount}


# get chama day and convert to string
@router.get(
    "/contribution_day/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_contrbution_day(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    contribution = (
        db.query(models.ChamaContributionDay)
        .filter(models.ChamaContributionDay.chama_id == chama_id)
        .first()
    )
    if not contribution:
        raise HTTPException(status_code=404, detail="Chama contribution day not found")
    return {
        "contribution_day": contribution.next_contribution_date.strftime("%A"),
        "contribution_date": contribution.next_contribution_date,
    }


# get the number of members in a given chama by chama id


# TODO: retrieve manager recent transactions and display beneath recent activity
