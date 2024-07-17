from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from sqlalchemy import func, update, and_, table, column, desc
from typing import List, Union
from sqlalchemy.exc import SQLAlchemyError

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/chamas", tags=["management"])

logger = logging.getLogger(__name__)

nairobi_tz = ZoneInfo("Africa/Nairobi")


# create chama for a logged in manager
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ChamaResp)
async def create_chama(
    chama: schemas.ChamaBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):

    try:
        chama_dict = chama.dict()
        chama_dict["manager_id"] = current_user.id
        chama_dict["date_created"] = datetime.now(nairobi_tz).replace(tzinfo=None)
        chama_dict["updated_at"] = datetime.now(nairobi_tz).replace(tzinfo=None)
        chama_dict["account_name"] = chama_dict["chama_name"].replace(" ", "").lower()

        new_chama = models.Chama(**chama_dict)
        db.add(new_chama)
        db.commit()
        db.refresh(new_chama)

        return {"Chama": [new_chama]}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create chama")


# retrive chama accepting chamas and are active
@router.get(
    "/active_accepting_members_chamas",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.ActivelyAcceptingMembersChamas],
)
async def get_active_chamas(
    db: Session = Depends(database.get_db),
):
    try:
        chamas = (
            db.query(models.Chama).filter(
                and_(
                    models.Chama.is_active == True,
                    models.Chama.accepting_members == True,
                )
            )
        ).all()

        if not chamas:
            raise HTTPException(status_code=404, detail="No active chamas found")

        return chamas
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to retrieve active chamas")


# TODO: set contribution day for a chama during creation using the first contribution date
@router.post("/set_first_contribution_date", status_code=status.HTTP_201_CREATED)
async def set_first_contribution_day(
    date_details: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        chama = (
            db.query(models.Chama)
            .filter(models.Chama.chama_name == date_details["chama_name"])
            .first()
        )

        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        chama_contribution_day = (
            db.query(models.ChamaContributionDay).filter_by(chama_id=chama.id).first()
        )

        if chama_contribution_day:
            chama_contribution_day.next_contribution_date = datetime.strptime(
                date_details["first_contribution_date"], "%Y-%m-%d"
            )
        else:
            first_contribution_date = datetime.strptime(
                date_details["first_contribution_date"], "%Y-%m-%dT%H:%M:%S"
            )
            new_record = models.ChamaContributionDay(
                chama_id=chama.id,
                next_contribution_date=first_contribution_date,
            )
            db.add(new_record)

        db.commit()
        return {"message": "Contribution day set successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to set contribution day")


# updating contribution days for chamas
@router.put("/update_contribution_days", status_code=status.HTTP_200_OK)
async def update_contribution_days(
    db: Session = Depends(database.get_db),
):

    try:
        # get chama_ids, contribution_interval, contribution_day from chamas
        chamas = db.query(models.Chama).all()
        for chama in chamas:
            contribution_interval = chama.contribution_interval
            contribution_day = chama.contribution_day

            upcoming_contribution_date = calculate_next_contribution_date(
                contribution_interval, contribution_day
            )
            print("=========upcoming_contribution_date============")
            print(upcoming_contribution_date)

            chama_contribution_day = (
                db.query(models.ChamaContributionDay)
                .filter_by(chama_id=chama.id)
                .first()
            )

            if chama_contribution_day:
                print("=========day exists============")
                print(chama_contribution_day.next_contribution_date)
                chama_contribution_day.next_contribution_date = (
                    upcoming_contribution_date
                )
                print("=========after============")
                print(chama_contribution_day.next_contribution_date)
            else:
                print("=========day does not exist============")
                new_record = models.ChamaContributionDay(
                    chama_id=chama.id, next_contribution_date=upcoming_contribution_date
                )
                db.add(new_record)

        db.commit()
        return {"message": "Contribution days updated successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to update contribution days"
        )


# ====================================================
def calculate_next_contribution_date(contribution_interval, contribution_day):
    # set timezone to kenya
    kenya_tz = ZoneInfo("Africa/Nairobi")
    today = datetime.now(kenya_tz).replace(tzinfo=None)
    logger.info(f"Today's date: {today}")
    logger.info(f"Contribution interval: {contribution_interval}")
    logger.info(f"Contribution day: {contribution_day}")
    print("=============================================")
    print(f"Today's date: {today}")
    print(f"Contribution interval: {contribution_interval}")
    print(f"Contribution day: {contribution_day}")

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
        next_contribution_date = today.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif contribution_interval == "weekly":
        today_index = today.weekday()
        contribution_day_index_value = contribution_day_index[
            contribution_day.capitalize()
        ]
        logger.info(f"Today's index: {today_index}")
        logger.info(f"Contribution day index: {contribution_day_index_value}")
        days_until_contribution_day = (contribution_day_index_value - today_index) % 7
        logger.info(f"Days until contribution day: {days_until_contribution_day}")
        if days_until_contribution_day == 0:
            # if today is the contribution day check if time is past the contribution time, if not, set the next contribution day to today else set it to next week
            # if today.time() < contribution_time:
            #     next_contribution_date = today
            if today.time() < datetime.strptime("00:00", "%H:%M").time():
                logger.info("Time is before contribution time")
                next_contribution_date = today
            else:
                logger.info("Time is after contribution time")
                next_contribution_date = today + timedelta(weeks=1)
        else:
            logger.info("Today is not the contribution day yet")
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
            next_month = next_month.replace(month=(next_month.month % 12) + 1)
        next_contribution_date = next_month
    print(f"Next contribution date: {next_contribution_date}")
    logger.info("=============================================")
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


# get chama by id for a logged in member
@router.get(
    "/{chama_id}", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def get_chama_by_name(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# getting the chama for a public user - no authentication required
# TODO: the table being querries should be chama_blog/details and not chama, description should match in both
@router.get(
    "/public_chama/{chama_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ChamaResp,
)
async def view_chama(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
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
    try:
        accepting_members = status["accepting_members"]
        chama_id = status["chama_id"]

        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        chama.accepting_members = accepting_members
        db.commit()
        return {"message": "Status updated successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to update status")


# member_to be added to chama on the member_chama_association table
@router.post("/join", status_code=status.HTTP_201_CREATED)
async def join_chama(
    member_chama: schemas.JoinChamaBase = Body(...),
    db: Session = Depends(database.get_db),
):
    member_chama = member_chama.dict()
    chama_id = member_chama["chama_id"]
    member_id = member_chama["member_id"]
    num_of_shares = member_chama["num_of_shares"]

    try:
        # Check if the member is already part of the chama

        with db.begin():
            new_member_chama = models.members_chamas_association.insert().values(
                chama_id=chama_id,
                member_id=member_id,
                num_of_shares=num_of_shares,
                date_joined=datetime.now(nairobi_tz).replace(tzinfo=None),
                registration_fee_paid=True,
            )
            db.execute(new_member_chama)
            db.flush()
        return {"message": "Member added to chama successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to add member to chama")


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
    print("==========chamaid chamaname============")
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chamaname).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama_id": chama.id}


# get chamas name from id
@router.get("/chama_name/{chama_id}", status_code=status.HTTP_200_OK)
async def get_chama_name(
    chama_id: int,
    db: Session = Depends(database.get_db),
):

    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama_name": chama.chama_name}


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

    account_dict = account.dict()
    chama_id = account_dict["chama_id"]
    new_amount = account_dict["amount_deposited"]
    transaction_type = account_dict["transaction_type"]

    try:
        print("=====updating account bal=========")
        with db.begin():
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == chama_id)
                .first()
            )

            if not chama_account and transaction_type == "deposit":
                chama_account = models.Chama_Account(
                    chama_id=chama_id, account_balance=new_amount
                )
                db.add(chama_account)
            elif chama_account and transaction_type == "deposit":
                chama_account.account_balance += new_amount
            elif chama_account and transaction_type == "withdraw":
                if chama_account.account_balance < new_amount:
                    raise HTTPException(
                        status_code=400, detail="Insufficient account balance"
                    )
                chama_account.account_balance -= new_amount
            else:
                raise HTTPException(
                    status_code=400, detail="Failed to update account balance"
                )

            db.flush()  # flush the changes to the database ensures that the changes are saved to the database
            # db.commit() - with db.begin() commits the transaction if all queries are successful, no need to commit manually
            db.refresh(
                chama_account
            )  # needed to refresh the object to get the updated values
        print("=====account bal updated=========")
        return chama_account

    except SQLAlchemyError as e:
        db.rollback()
        print("------update acc error--------")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to update account balance")
    except Exception as e:
        db.rollback()
        print("------update acc error--------")
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
    current_user: Union[models.Manager, models.Member] = Depends(
        oauth2.get_current_user
    ),
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
    current_user: Union[models.Manager, models.Member] = Depends(
        oauth2.get_current_user
    ),
):
    today = datetime.now(nairobi_tz).date()
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
        "contribution_date": contribution.next_contribution_date.strftime("%d-%B-%Y"),
    }


# get chama contribution interval
@router.get(
    "/contribution_interval/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_contrbution_interval(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {
        "contribution_interval": chama.contribution_interval,
        "contribution_day": chama.contribution_day,
    }


# get chamas registration fee
@router.get("/registration_fee/{chama_id}", status_code=status.HTTP_200_OK)
async def get_chama_registration_fee(
    chama_id: int,
    db: Session = Depends(database.get_db),
):

    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")

    return {"registration_fee": chama.registration_fee}


# count the number of members in a certain chama
@router.get(
    "/members_count/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_members_count(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: Union[models.Manager, models.Member] = Depends(
        oauth2.get_current_user
    ),
):
    chama_members_query = db.query(models.members_chamas_association).filter(
        models.members_chamas_association.c.chama_id == chama_id
    )
    number_of_members = chama_members_query.count()
    if not chama_members_query:
        raise HTTPException(
            status_code=404, detail="could not retrieve chama members count"
        )
    return {"number_of_members": number_of_members}


@router.get(
    "/count_members/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_members_count(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    chama_members_query = db.query(models.members_chamas_association).filter(
        models.members_chamas_association.c.chama_id == chama_id
    )
    number_of_members = chama_members_query.count()
    if not chama_members_query:
        raise HTTPException(
            status_code=404, detail="could not retrieve chama members count"
        )
    return {"number_of_members": number_of_members}


# activate and deactivate chama
@router.put("/activate_deactivate", status_code=status.HTTP_200_OK)
async def activate_chama(
    chama: schemas.ChamaActivateDeactivate = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    chama_dict = chama.dict()
    chama_id = chama_dict["chama_id"]
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    chama.is_active = chama_dict["is_active"]
    db.commit()
    return {"message": "Chama activated/deactivated successfully"}


# delete chama id
@router.delete("/delete_chama", status_code=status.HTTP_200_OK)
async def delete_chama(
    chama: schemas.ChamaDeleteBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        chama_dict = chama.dict()
        chama_id = chama_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        db.delete(chama)
        db.commit()
        return {"message": "Chama deleted successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to delete chama")


# get chamas creation date
@router.get(
    "/creation_date/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_creation_date(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")

    return {"creation_date": chama.date_created.strftime("%d-%m-%Y")}


# get chamas start date
@router.get(
    "/start_date/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_start_date(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")

    return {"start_date": chama.last_joining_date.strftime("%d-%m-%Y")}


# get chama about by id from (rules, description, mission, vision, faqs)
@router.get(
    "/about_chama/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_about(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: Union[models.Manager, models.Member] = Depends(
        oauth2.get_current_user
    ),
):
    print("=============================================")
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        chama_rules = db.query(models.Rule).filter(models.Rule.chama_id == chama_id)
        chama_rules_dict = {}
        for rule in chama_rules:
            chama_rules_dict[rule.id] = rule.rule

        about_chama = (
            db.query(models.About_Chama)
            .filter(models.About_Chama.chama_id == chama_id)
            .first()
        )

        chama_faqs = db.query(models.Faq).filter(models.Faq.chama_id == chama_id)
        # id, question, answer
        chama_faqs_list = [
            {"id": faq.id, "question": faq.question, "answer": faq.answer}
            for faq in chama_faqs
        ]

        return {
            "chama": chama,
            "rules": chama_rules_dict,
            "about": about_chama,
            "faqs": chama_faqs_list,
        }
    except Exception as e:
        print("=============================================")
        print(e)
        raise HTTPException(status_code=400, detail="Failed to retrieve chama about")


# update chama description
@router.put("/update_description", status_code=status.HTTP_200_OK)
async def update_chama_description(
    description: schemas.ChamaDescription = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        description_dict = description.dict()
        chama_id = description_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        chama.description = description_dict["description"]
        db.commit()

        return {"message": "Chama description updated successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to update chama description"
        )


# update chama vision
@router.put("/update_vision", status_code=status.HTTP_200_OK)
async def update_chama_vision(
    vision: schemas.ChamaVision = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        vision_dict = vision.dict()
        chama_id = vision_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        about_chama = (
            db.query(models.About_Chama)
            .filter(models.About_Chama.chama_id == chama_id)
            .first()
        )
        print("about_chama", about_chama, chama.id)
        if chama and not about_chama:
            print("===chama wtihout about===")
            new_about_chama = models.About_Chama(
                chama_id=chama_id,
                manager_id=chama.manager_id,
                vision=vision_dict["vision"],
            )
            db.add(new_about_chama)
            db.commit()
            db.refresh(new_about_chama)
        elif chama and about_chama:
            print("===chama with about===")
            about_chama.vision = vision_dict["vision"]
            db.commit()
            db.refresh(about_chama)

        return {"message": "Chama vision updated successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to update chama vision")


@router.put("/update_mission", status_code=status.HTTP_200_OK)
async def update_chama_mission(
    mission: schemas.ChamaMission = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        print("==================hit====================")
        mission_dict = mission.dict()
        chama_id = mission_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()

        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        about_chama = (
            db.query(models.About_Chama)
            .filter(models.About_Chama.chama_id == chama_id)
            .first()
        )

        if chama and not about_chama:
            new_about_chama = models.About_Chama(
                chama_id=chama_id,
                manager_id=chama.manager_id,
                mission=mission_dict["mission"],
            )
            db.add(new_about_chama)
            db.commit()
            db.refresh(new_about_chama)
        elif chama and about_chama:
            about_chama.mission = mission_dict["mission"]
            db.commit()
            db.refresh(about_chama)

        return {"message": "Chama mission updated successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to update chama mission")


# add a rule to a chama
@router.post("/add_rule", status_code=status.HTTP_201_CREATED)
async def add_rule(
    rule: schemas.ChamaRuleBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        rule_dict = rule.dict()
        chama_id = rule_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        chama_rules = db.query(models.Rule).filter(models.Rule.chama_id == chama_id)
        new_rule = models.Rule(chama_id=chama_id, rule=rule_dict["rule"])
        db.add(new_rule)
        db.commit()
        db.refresh(new_rule)

        return {"message": "Rule added successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to add rule")


# edit a rule in a chama


# delete a rule in a chama
@router.delete("/delete_rule", status_code=status.HTTP_200_OK)
async def delete_rule(
    rule: schemas.ChamaRuleDeleteBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        rule_dict = rule.dict()
        chama_id = rule_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        rule_to_delete = (
            db.query(models.Rule)
            .filter_by(chama_id=chama_id, id=rule_dict["rule_id"])
            .first()
        )
        if not rule_to_delete:
            raise HTTPException(status_code=404, detail="Rule not found")

        db.delete(rule_to_delete)
        db.commit()

        return {"message": "Rule deleted successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to delete rule")


# add an faq question snd answer to a faq tbalr
@router.post("/add_faq", status_code=status.HTTP_201_CREATED)
async def add_faq(
    faq: schemas.ChamaFaqBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        faq_dict = faq.dict()
        chama_id = faq_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        chama_faqs = db.query(models.Faq).filter(models.Faq.chama_id == chama_id)
        new_faq = models.Faq(
            chama_id=chama_id,
            question=faq_dict["question"],
            answer=faq_dict["answer"],
        )
        db.add(new_faq)
        db.commit()
        db.refresh(new_faq)

        return {"message": "Faq added successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to add faq")


# delete a faq in a chama
@router.delete("/delete_faq", status_code=status.HTTP_200_OK)
async def delete_faq(
    faq: schemas.ChamaFaqDeleteBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        faq_dict = faq.dict()
        chama_id = faq_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        faq_to_delete = (
            db.query(models.Faq)
            .filter_by(chama_id=chama_id, id=faq_dict["faq_id"])
            .first()
        )
        if not faq_to_delete:
            raise HTTPException(status_code=404, detail="Faq not found")

        db.delete(faq_to_delete)
        db.commit()

        return {"message": "Faq deleted successfully"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to delete faq")


# get the faqs of a chama
@router.get(
    "/faqs/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_faqs(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama_faqs = db.query(models.Faq).filter(models.Faq.chama_id == chama_id)
        if not chama_faqs:
            raise HTTPException(status_code=404, detail="Chama faqs not found")
        return {
            "faqs": [
                {"question": faq.question, "answer": faq.answer} for faq in chama_faqs
            ]
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to retrieve chama faqs")


# get the rules of a chama
@router.get(
    "/rules/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_rules(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama_rules = db.query(models.Rule).filter(models.Rule.chama_id == chama_id)
        if not chama_rules:
            raise HTTPException(status_code=404, detail="Chama rules not found")
        return [rule.rule for rule in chama_rules]
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to retrieve chama rules")


# get mission and vision of a chama
@router.get(
    "/mission/vision/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_mission_vision(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        about_chama = (
            db.query(models.About_Chama)
            .filter(models.About_Chama.chama_id == chama_id)
            .first()
        )
        if not about_chama:
            raise HTTPException(
                status_code=404, detail="Chama mission and vision not found"
            )
        return {"mission": about_chama.mission, "vision": about_chama.vision}
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama mission and vision"
        )


# retrive all chamas share price, and previous two contribution dates
# i wll use date from the upcoming contribution date to get the previous two contribution dates by subtracting the contribution interval
@router.get(
    "/calculate_fines",
    status_code=status.HTTP_200_OK,
)
async def get_share_price_and_prev_two_contribution_dates(
    db: Session = Depends(database.get_db),
):
    try:
        chamas = db.query(models.Chama).all()
        chamas_details = {}
        for chama in chamas:
            chama_contribution_day = (
                db.query(models.ChamaContributionDay)
                .filter(models.ChamaContributionDay.chama_id == chama.id)
                .first()
            )
            if not chama_contribution_day:
                raise HTTPException(
                    status_code=404, detail="Chama contribution day not found"
                )

            print("================contributions==================")
            print(chama.contribution_interval)
            print(chama_contribution_day.next_contribution_date)

            prev_contribution_date, prev_two_contribution_date = (
                calculate_two_previous_dates(
                    chama.contribution_interval,
                    chama_contribution_day.next_contribution_date,
                )
            )

            print(prev_contribution_date, "::", prev_two_contribution_date)
            print("================contributions==================")
            chamas_details[chama.id] = {
                "share_price": chama.contribution_amount,
                "fine_per_share": chama.fine_per_share,
                "prev_contribution_date": prev_contribution_date,
                "prev_two_contribution_date": prev_two_contribution_date,
            }

        return chamas_details
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400,
            detail="Failed to retrieve chamas share price and previous two contribution dates",
        )


# retrieve all fines for a chama - where is_paid is False
@router.get(
    "/fines/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_fines(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        with db.begin():
            # Retrieve the latest 10 fines where is_paid is False
            chama_fines = (
                db.query(models.Fine)
                .filter(models.Fine.chama_id == chama_id)
                .filter(models.Fine.is_paid == False)
                .order_by(desc(models.Fine.fine_date))
                .limit(10)
                .all()
            )
            if not chama_fines:
                return {"fines": []}

            # Extract member IDs from the retrieved fines
            member_ids = [fine.member_id for fine in chama_fines]

            # Retrieve the number of shares for each member in the member_ids list
            shares_number = (
                db.query(models.members_chamas_association)
                .filter(models.members_chamas_association.c.chama_id == chama_id)
                .filter(models.members_chamas_association.c.member_id.in_(member_ids))
                .all()
            )

        return {
            "fines": [
                {
                    "member_id": fine.member_id,
                    "num_of_shares": next(
                        (
                            shares.num_of_shares
                            for shares in shares_number
                            if shares.member_id == fine.member_id
                        ),
                        0,
                    ),
                    "fine": fine.fine,
                    "fine_reason": fine.fine_reason,
                    "fine_date": fine.fine_date.strftime("%d-%m-%Y"),
                    "total_expected_amount": fine.total_expected_amount,
                    "cleared": "No" if not fine.is_paid else "Yes",
                }
                for fine in chama_fines
            ]
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to retrieve chama fines")


# retrieve all fines for a chama, paid or not
@router.get(
    "/all_fines/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_all_fines(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama_fines = (
            db.query(models.Fine).filter(models.Fine.chama_id == chama_id).all()
        )
        if not chama_fines:
            raise HTTPException(status_code=404, detail="Chama fines not found")

        shares = (
            db.query(models.members_chamas_association)
            .filter(models.members_chamas_association.c.chama_id == chama_id)
            .all()
        )

        return {
            "fines": [
                {
                    "member_id": fine.member_id,
                    "num_of_shares": [
                        share.num_of_shares
                        for share in shares
                        if share.member_id == fine.member_id
                    ][0],
                    "fine": fine.fine,
                    "fine_reason": fine.fine_reason,
                    "fine_date": fine.fine_date.strftime("%d-%m-%Y"),
                    "total_expected_amount": fine.total_expected_amount,
                    "is_paid": "NO" if fine.is_paid == False else "YES",
                    "paid_date": (
                        fine.paid_date.strftime("%d-%m-%Y") if fine.paid_date else ""
                    ),
                }
                for fine in chama_fines
            ]
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to retrieve chama fines")
