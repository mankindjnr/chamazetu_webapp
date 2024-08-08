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

management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")

nairobi_tz = ZoneInfo("Africa/Nairobi")


# create chama for a logged in manager
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ChamaResp)
async def create_chama(
    chama: schemas.ChamaBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):

    chama_dict = chama.dict()
    chama_dict["manager_id"] = current_user.id
    chama_dict["date_created"] = datetime.now(nairobi_tz).replace(tzinfo=None)
    chama_dict["updated_at"] = datetime.now(nairobi_tz).replace(tzinfo=None)
    chama_dict["account_name"] = chama_dict["chama_name"].replace(" ", "").lower()
    # TODO: add he chama code for offline payments here

    new_chama = models.Chama(**chama_dict)

    try:
        db.add(new_chama)
        db.commit()
        db.refresh(new_chama)

        return {"Chama": [new_chama]}
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"failed to create chama, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to create chama")
    finally:
        db.close()  # close the database connection


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
        management_error_logger.error(f"failed to retrieve active chamas, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve active chamas")
    finally:
        db.close()


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
        management_error_logger.error(
            f"failed to set contribution day for: {chama.id}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to set contribution day")
    finally:
        db.close()


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
            management_info_logger.info(f"interval: {contribution_interval}")
            management_info_logger.info(f"day: {contribution_day}")
            management_info_logger.info(
                f"upcoming_contribution_date: {upcoming_contribution_date}"
            )

            chama_contribution_day = (
                db.query(models.ChamaContributionDay)
                .filter_by(chama_id=chama.id)
                .first()
            )

            if chama_contribution_day:
                chama_contribution_day.next_contribution_date = (
                    upcoming_contribution_date
                )
            else:
                new_record = models.ChamaContributionDay(
                    chama_id=chama.id, next_contribution_date=upcoming_contribution_date
                )
                db.add(new_record)

        db.commit()
        return {"message": "Contribution days updated successfully"}
    except Exception as e:
        db.rollback()
        management_error_logger.error(
            f"failed to update contribution days for: {chama.id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to update contribution days"
        )
    finally:
        db.close()


# ====================================================
def calculate_next_contribution_date(contribution_interval, contribution_day):
    # set timezone to kenya
    kenya_tz = ZoneInfo("Africa/Nairobi")
    today = datetime.now(kenya_tz).replace(tzinfo=None)
    management_info_logger.info(f"Today's date: {today}")
    management_info_logger.info(f"Contribution interval: {contribution_interval}")
    management_info_logger.info(f"Contribution day: {contribution_day}")

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
        management_info_logger.info(f"Today's index: {today_index}")
        management_info_logger.info(
            f"Contribution day index: {contribution_day_index_value}"
        )
        days_until_contribution_day = (contribution_day_index_value - today_index) % 7
        management_info_logger.info(
            f"Days until contribution day: {days_until_contribution_day}"
        )
        if days_until_contribution_day == 0:
            management_info_logger.info("Today is the contribution day")
            next_contribution_date = today
        else:
            management_info_logger.info("Today is not the contribution day yet")
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

    management_info_logger.info(f"Next contribution date: {next_contribution_date}")
    management_info_logger.info("=============================================")
    # return the next contribution date with no microseconds seconds and minutes zeor
    return next_contribution_date.replace(hour=0, minute=0, second=0, microsecond=0)


# ====================================================


# get chama by name for a logged in manager
@router.get("/", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp)
async def get_chama_by_name(
    chama_name: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        chama_name = chama_name["chama_name"]
        chama = (
            db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
        )
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama": [chama]}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by name for: {chama_name}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by name")
    finally:
        db.close()


# get chama by id for a logged in member
@router.get("/chama", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp)
async def get_chama_by_id(
    chama_id: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    try:
        chama_id = chama_id["chamaid"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama": [chama]}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by id for: {chama_id}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by id")
    finally:
        db.close()


# retrive the next contribution date
@router.get("/next_contribution_date/{chama_id}", status_code=status.HTTP_200_OK)
async def get_next_contribution_date(
    chama_id: int,
    db: Session = Depends(database.get_db),
):

    try:
        chama_contribution_day = (
            db.query(models.ChamaContributionDay)
            .filter(models.ChamaContributionDay.chama_id == chama_id)
            .first()
        )

        if not chama_contribution_day:
            raise HTTPException(
                status_code=404, detail="Chama contribution day not found"
            )

        # return as a datetime objet
        return {"next_contribution_date": chama_contribution_day.next_contribution_date}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama contribution day for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama contribution day"
        )
    finally:
        db.close()


# get chama by name for a logged in member
@router.get(
    "/chama_name", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def get_chama_by_name(
    chama_name: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    try:
        chama_name = chama_name["chamaname"]
        chama = (
            db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
        )
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama": [chama]}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by name for: {chama_name}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by name")
    finally:
        db.close()


# get chama by id for a logged in member
@router.get(
    "/{chama_id}", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def get_chama_by_name(
    chama_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama": [chama]}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by id for: {chama_id}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by id")
    finally:
        db.close()


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
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        # we will use the id to extract the manager details like profile photo
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama": [chama]}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by id for: {chama_id}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by id")
    finally:
        db.close()


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
    finally:
        db.close()


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
    try:
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
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=400, detail="Failed to add shares")
    finally:
        db.close()


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
    try:
        chamaids = chamaids["chamaids"]
        chamas = db.query(models.Chama).filter(models.Chama.id.in_(chamaids)).all()
        if not chamas:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama": chamas}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by id for: {chamaids}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by id")
    finally:
        db.close()


# retrieving chama id from its name
@router.get("/chama_id/{chamaname}", status_code=status.HTTP_200_OK)
async def get_chama_id(
    chamaname: str,
    db: Session = Depends(database.get_db),
):
    try:
        chama = (
            db.query(models.Chama).filter(models.Chama.chama_name == chamaname).first()
        )
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama_id": chama.id}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by name for: {chamaname}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by name")
    finally:
        db.close()


# get chamas name from id
@router.get("/chama_name/{chama_id}", status_code=status.HTTP_200_OK)
async def get_chama_name(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Chama_name": chama.chama_name}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama by id for: {chama_id}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by id")
    finally:
        db.close()


# retrieving all member ids of a chama
@router.get("/members/{chama_id}", status_code=status.HTTP_200_OK)
async def get_chama_members(
    chama_id: str,
    db: Session = Depends(database.get_db),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {"Members": [member.id for member in chama.members]}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama members for: {chama_id}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama members")
    finally:
        db.close()


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
            db.refresh(chama_account)
        return chama_account

    except SQLAlchemyError as e:
        db.rollback()
        management_error_logger.error(f"failed to update account balance, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to update account balance")
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"failed to update account balance, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to update account balance")
    finally:
        db.close()


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
    try:
        chama_account_balance = (
            db.query(models.Chama_Account)
            .filter(models.Chama_Account.chama_id == chama_id)
            .first()
        )
        if not chama_account_balance:
            raise HTTPException(status_code=404, detail="Chama account not found")
        return chama_account_balance
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama account balance for: {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama account balance"
        )
    finally:
        db.close()


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

    try:
        total_amount = (
            db.query(func.coalesce(func.sum(models.Transaction.amount), 0))
            .filter(models.Transaction.chama_id == chama_id)
            .filter(models.Transaction.transaction_type == "deposit")
            .filter(func.date(models.Transaction.date_of_transaction) == today)
            .scalar()
        )

        total_fines = 0
        if current_user.is_member:
            total_fines = (
                db.query(func.coalesce(func.sum(models.Fine.total_expected_amount), 0))
                .filter(
                    and_(
                        models.Fine.chama_id == chama_id,
                        models.Fine.member_id == current_user.id,
                        models.Fine.is_paid == False,
                    )
                )
                .scalar()
            )

        return {"today_deposits": total_amount, "total_fines": total_fines}
    except Exception as e:
        db.rollback()
        management_error_logger.error(
            f"failed to get today's deposits for chama: {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve today's deposits"
        )
    finally:
        db.close()


# get chama day and convert to string
@router.get(
    "/contribution_day/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_contrbution_day(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        contribution = (
            db.query(models.ChamaContributionDay)
            .filter(models.ChamaContributionDay.chama_id == chama_id)
            .first()
        )
        if not contribution:
            raise HTTPException(
                status_code=404, detail="Chama contribution day not found"
            )
        return {
            "contribution_day": contribution.next_contribution_date.strftime("%A"),
            "contribution_date": contribution.next_contribution_date.strftime(
                "%d-%B-%Y"
            ),
        }
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama contribution day for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama contribution day"
        )
    finally:
        db.close()


# get chama contribution interval
@router.get(
    "/contribution_interval/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_contrbution_interval(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        return {
            "contribution_interval": chama.contribution_interval,
            "contribution_day": chama.contribution_day,
        }
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama contribution interval for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama contribution interval"
        )
    finally:
        db.close()


# get chamas registration fee
@router.get("/registration_fee/{chama_id}", status_code=status.HTTP_200_OK)
async def get_chama_registration_fee(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        return {"registration_fee": chama.registration_fee}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama registration fee for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama registration fee"
        )
    finally:
        db.close()


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
    try:
        number_of_members = (
            db.query(func.count(models.members_chamas_association.c.member_id))
            .filter(models.members_chamas_association.c.chama_id == chama_id)
            .scalar()
        )

        if number_of_members == 0:
            raise HTTPException(status_code=404, detail="No members found")
        return {"number_of_members": number_of_members}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama members count for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama members count"
        )
    finally:
        db.close()


@router.get(
    "/count_members/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_members_count(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        number_of_members = (
            db.query(func.count(models.members_chamas_association.c.member_id))
            .filter(models.members_chamas_association.c.chama_id == chama_id)
            .scalar()
        )

        if number_of_members == 0:
            raise HTTPException(status_code=404, detail="No members found")
        return {"number_of_members": number_of_members}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama members count for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama members count"
        )


# activate and deactivate chama
@router.put("/activate_deactivate", status_code=status.HTTP_200_OK)
async def activate_chama(
    chama: schemas.ChamaActivateDeactivate = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        chama_dict = chama.dict()
        chama_id = chama_dict["chama_id"]
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")
        chama.is_active = chama_dict["is_active"]
        db.commit()
        return {"message": "Chama activated/deactivated successfully"}
    except Exception as e:
        db.rollback()
        management_error_logger.error(
            f"failed to activate/deactivate chama, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to activate/deactivate chama"
        )
    finally:
        db.close()


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
        management_error_logger.error(f"failed to delete chama, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to delete chama")
    finally:
        db.close()


# get chamas creation date
@router.get(
    "/creation_date/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_creation_date(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        return {"creation_date": chama.date_created.strftime("%d-%m-%Y")}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama creation date for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama creation date"
        )
    finally:
        db.close()


# get chamas start date
@router.get(
    "/start_date/{chama_id}",
    status_code=status.HTTP_200_OK,
)
async def get_chama_start_date(
    chama_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        return {"start_date": chama.last_joining_date.strftime("%d-%m-%Y")}
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama start date for id {chama_id}, error: {e}"
        )
        raise HTTPException(
            status_code=400, detail="Failed to retrieve chama start date"
        )
    finally:
        db.close()


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
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        chama_rules = db.query(models.Rule).filter(models.Rule.chama_id == chama_id)
        chama_rules_dict = {rule.id: rule.rule for rule in chama_rules}

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
    except SQLAlchemyError as e:
        management_error_logger.error(
            f"failed to get chama about for id {chama_id}, error: {e}"
        )
        raise HTTPException(status_code=400, detail="Failed to retrieve chama about")
    except Exception as e:
        management_error_logger.error(
            f"failed to get chama about for id {chama_id}, error: {e}"
        )
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
        if not about_chama:
            new_about_chama = models.About_Chama(
                chama_id=chama_id,
                manager_id=chama.manager_id,
                vision=vision_dict["vision"],
            )
            db.add(new_about_chama)
        else:
            about_chama.vision = vision_dict["vision"]
        db.commit()

        return {"message": "Chama vision updated successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        management_error_logger.error(f"failed to update chama vision, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to update chama vision")
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"failed to update chama vision, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to update chama vision")


@router.put("/update_mission", status_code=status.HTTP_200_OK)
async def update_chama_mission(
    mission: schemas.ChamaMission = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
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

        if not about_chama:
            new_about_chama = models.About_Chama(
                chama_id=chama_id,
                manager_id=chama.manager_id,
                mission=mission_dict["mission"],
            )
            db.add(new_about_chama)
        else:
            about_chama.mission = mission_dict["mission"]
        db.commit()

        return {"message": "Chama mission updated successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        management_error_logger.error(f"failed to update chama mission, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to update chama mission")
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

        new_rule = models.Rule(chama_id=chama_id, rule=rule_dict["rule"])
        db.add(new_rule)
        db.commit()
        db.refresh(new_rule)

        return {"message": "Rule added successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        management_error_logger.error(f"failed to add rule, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to add rule")
    except Exception as e:
        db.rollback()
        management_error_logger.error(f"failed to add rule, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to add rule")


# edit a rule in a chama


# utility function to get a chama by id
def get_chama_by_id_func(db, chama_id):
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return chama


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
        chama = get_chama_by_id_func(db, chama_id)

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
        chama = get_chama_by_id_func(db, chama_id)

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
        management_error_logger.error(f"failed to add faq, error: {e}")
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
        chama = get_chama_by_id_func(db, chama_id)

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
        chama_faqs = db.query(models.Faq).filter(models.Faq.chama_id == chama_id).all()
        if not chama_faqs:
            raise HTTPException(status_code=404, detail="Chama faqs not found")
        return {
            "faqs": [
                {"question": faq.question, "answer": faq.answer} for faq in chama_faqs
            ]
        }
    except Exception as e:
        management_error_logger.error(f"failed to get chama faqs, error: {e}")
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
        chama_rules = (
            db.query(models.Rule).filter(models.Rule.chama_id == chama_id).all()
        )
        if not chama_rules:
            raise HTTPException(status_code=404, detail="Chama rules not found")
        return [rule.rule for rule in chama_rules]
    except Exception as e:
        management_error_logger.error(f"failed to get chama rules, error: {e}")
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
        management_error_logger.error(
            f"failed to get chama mission and vision for id {chama_id}, error: {e}"
        )
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

            prev_contribution_date, prev_two_contribution_date = (
                calculate_two_previous_dates(
                    chama.contribution_interval,
                    chama_contribution_day.next_contribution_date,
                )
            )

            chamas_details[chama.id] = {
                "share_price": chama.contribution_amount,
                "fine_per_share": chama.fine_per_share,
                "prev_contribution_date": prev_contribution_date,
                "prev_two_contribution_date": prev_two_contribution_date,
            }

        return chamas_details
    except Exception as e:
        management_error_logger.error(
            f"failed to get chamas share price and previous two contribution dates, error: {e}"
        )
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
        management_error_logger.error(f"failed to get chama fines, error: {e}")
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
