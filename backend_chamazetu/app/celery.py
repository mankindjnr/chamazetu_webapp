from celery import Celery
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from sqlalchemy import and_, func, desc
from uuid import uuid4
from typing import List
import httpx
import logging
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv


load_dotenv()


from . import schemas, database, utils, oauth2, models

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")

nairobi_tz = ZoneInfo("Africa/Nairobi")


celery_app = Celery(
    "chamazetu_backend",
    broker="redis://backend_message_broker:6379/0",  # Use the message broker from Docker
    backend="redis://backend_message_broker:6379/1"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=ZoneInfo("Africa/Nairobi"),
    enable_utc=False,
)



@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_callback(self, unprocessed_code: str, transaction_data: dict):
    db: Session = next(database.get_db())
    try:
        response_code = transaction_data["Body"]["stkCallback"]["ResultCode"]
        if not response_code == 0:
            raise HTTPException(status_code=400, detail="The service request failed.")

        today = datetime.now(nairobi_tz).date()
        amount = int(
            transaction_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0][
                "Value"
            ]
        )
        result_desc = transaction_data["Body"]["stkCallback"]["ResultDesc"]
        mpesa_receipt_number = transaction_data["Body"]["stkCallback"][
            "CallbackMetadata"
        ]["Item"][1]["Value"]

        print("into the transaction date")
        print(transaction_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][3]["Value"])
        transaction_date_str = str(transaction_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][3]["Value"])[:14]
        transaction_date = datetime.strptime(transaction_date_str, "%Y%m%d%H%M%S")
        phone_number = str(
            transaction_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][4][
                "Value"
            ]
        )
        if len(phone_number) == 10:
            phone_number = f"254{phone_number[1:]}"
        # retrieve unprocessed transaction from the database
        unprocessed_deposit = (
            db.query(models.WalletTransaction)
            .filter(
                and_(
                    models.WalletTransaction.transaction_type
                    == "unprocessed wallet deposit",
                    models.WalletTransaction.transaction_completed == False,
                    models.WalletTransaction.transaction_code == unprocessed_code,
                    func.date(models.WalletTransaction.transaction_date) == today,
                    models.WalletTransaction.amount == amount,
                    models.WalletTransaction.origin == phone_number,
                )
            )
            .first()
        )

        if not unprocessed_deposit:
            raise HTTPException(
                status_code=404, detail="Unprocessed deposit transaction not found"
            )

        # update user's wallet balance
        user = (
            db.query(models.User)
            .filter(models.User.id == unprocessed_deposit.user_id)
            .first()
        )

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.wallet_balance += amount

        # update the transaction status to processed as deposit since its completed transaction
        unprocessed_deposit.transaction_completed = True
        unprocessed_deposit.transaction_type = "deposit"
        unprocessed_deposit.transaction_code = mpesa_receipt_number
        unprocessed_deposit.transaction_date = transaction_date

        # record tthe transaction in the callback table
        new_callback = models.CallbackData(
            MerchantRequestID=transaction_data["Body"]["stkCallback"][
                "MerchantRequestID"
            ],
            CheckoutRequestID=transaction_data["Body"]["stkCallback"][
                "CheckoutRequestID"
            ],
            ResultCode=response_code,
            ResultDesc=result_desc,
            Amount=amount,
            MpesaReceiptNumber=mpesa_receipt_number,
            TransactionDate=transaction_date,
            PhoneNumber=phone_number,
            Purpose="wallet",
            Status="Success",
        )
        db.add(new_callback)
        db.commit()
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to update transaction\n: {str(e)}")

        # retry the task
        try:
            self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            raise HTTPException(status_code=500, detail="Failed to update transaction")

@celery_app.task
def chama_registration_callback(unprocessed_code: str, registration_data: dict):
    db: Session = next(database.get_db())

    try:
        print("====regi data=====")
        # print(registration_data)

        response_code = registration_data["Body"]["stkCallback"]["ResultCode"]
        if response_code != 0:
            raise HTTPException(status_code=400, detail="The service request failed.")

        today = datetime.now(nairobi_tz).date()
        amount = int(
            registration_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0][
                "Value"
            ]
        )
        result_desc = registration_data["Body"]["stkCallback"]["ResultDesc"]
        mpesa_receipt_number = registration_data["Body"]["stkCallback"][
            "CallbackMetadata"
        ]["Item"][1]["Value"]
        transaction_date = datetime.strptime(
            str(
                registration_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][3][
                    "Value"
                ]
            ),
            "%Y%m%d%H%M%S",
        )
        phone_number = str(
            registration_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][4][
                "Value"
            ]
        )
        if len(phone_number) == 10:
            phone_number = f"254{phone_number[1:]}"

        db.begin()

        # retrieve unprocessed transaction from the database
        unprocessed_registration = (
            db.query(models.WalletTransaction)
            .filter(
                and_(
                    models.WalletTransaction.transaction_type
                    == "unprocessed registration fee",
                    models.WalletTransaction.transaction_completed == False,
                    models.WalletTransaction.transaction_code == unprocessed_code,
                    func.date(models.WalletTransaction.transaction_date) == today,
                    models.WalletTransaction.amount == amount,
                    models.WalletTransaction.origin == phone_number,
                )
            )
            .first()
        )

        if not unprocessed_registration:
            db.rollback()
            raise HTTPException(
                status_code=404, detail="Unprocessed registration transaction not found"
            )

        chama_id = int(unprocessed_registration.destination[:-12])
        reg_fee = (
            db.query(models.Chama.registration_fee)
            .filter(models.Chama.id == chama_id)
            .scalar()
        )

        if not reg_fee:
            db.rollback()
            raise HTTPException(status_code=404, detail="Registration fee not found")

        user = (
            db.query(models.User)
            .filter(models.User.id == unprocessed_registration.user_id)
            .with_for_update()
            .first()
        )

        if not user:
            db.rollback()
            raise HTTPException(status_code=404, detail="User not found")

        chamazetu_fee = 0.1 * reg_fee
        registration_to_chama = reg_fee - chamazetu_fee

        # Insert the new member to chamas
        new_member = models.chama_user_association.insert().values(
            chama_id=chama_id,
            user_id=user.id,
            date_joined=datetime.now(nairobi_tz).replace(tzinfo=None, microsecond=0),
            registration_fee_paid=True,
        )
        db.execute(new_member)

        # update the chama account balance
        chama_account = (
            db.query(models.Chama_Account)
            .filter(models.Chama_Account.chama_id == chama_id)
            .with_for_update()
            .first()
        )
        if not chama_account:
            db.rollback()
            raise HTTPException(status_code=404, detail="Chama account not found")

        chama_account.account_balance += registration_to_chama
        chama_account.available_balance += registration_to_chama

        # update the chamazetu account balance
        chamazetu_reg_account = (
            db.query(models.ChamaZetu).filter_by(id=1).with_for_update().first()
        )
        if not chamazetu_reg_account:
            db.rollback()
            raise HTTPException(status_code=404, detail="Chamazetu account not found")

        chamazetu_reg_account.registration_fees += chamazetu_fee

        # update the transaction status to processed as deposit since its completed transaction
        unprocessed_registration.transaction_completed = True
        unprocessed_registration.transaction_type = "registration"
        unprocessed_registration.transaction_code = mpesa_receipt_number
        unprocessed_registration.transaction_date = transaction_date

        # record the transaction in the callback table
        new_callback = models.CallbackData(
            MerchantRequestID=registration_data["Body"]["stkCallback"][
                "MerchantRequestID"
            ],
            CheckoutRequestID=registration_data["Body"]["stkCallback"][
                "CheckoutRequestID"
            ],
            ResultCode=response_code,
            ResultDesc=result_desc,
            Amount=amount,
            MpesaReceiptNumber=mpesa_receipt_number,
            TransactionDate=transaction_date,
            PhoneNumber=phone_number,
            Purpose="Registration",
            Status="Success",
        )

        db.add(new_callback)

        db.commit()
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to update transaction\n: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")


def get_phone_number(result):
    phone_number = result["Result"]["ResultParameters"]["ResultParameter"][2][
        "Value"
    ].split(" - ")[0]

    if len(phone_number) == 10:
        return f"254{phone_number[1:]}"

    return phone_number


def extract_originator_conversation_id(result: dict) -> str:
    return result.get("Result", {}).get("OriginatorConversationID", "")


def convert_date_format(date_str: str) -> str:
    # Define the current format of the date string
    current_format = "%d.%m.%Y %H:%M:%S"

    # Define the desired output format
    desired_format = "%Y-%m-%d %H:%M:%S"

    # Parse the input date string into a datetime object
    date_obj = datetime.strptime(date_str, current_format)

    # Convert the datetime object to the desired string format
    formatted_date = date_obj.strftime(desired_format)

    return formatted_date

def extract_result_parameters(result: dict) -> dict:
    result_parameters = result["Result"]["ResultParameters"]["ResultParameter"]
    extracted_result = {param["Key"]: param["Value"] for param in result_parameters}
    return extracted_result

@celery_app.task
def process_b2c_result(result: dict):
    db: Session = next(database.get_db())
    try:
        transaction_info_logger.info(f"Result: {result}")
        today = datetime.now(nairobi_tz).date()

        phone_number = get_phone_number(result)
        result_dict = extract_result_parameters(result)
        originator_conversation_id = extract_originator_conversation_id(result)
        completion_date = convert_date_format(
            result_dict["TransactionCompletedDateTime"]
        )

        db.begin()
        # retrieve unprocessed transactions from the database
        unprocessed_withdrawal = (
            db.query(models.WalletTransaction)
            .filter(
                and_(
                    models.WalletTransaction.transaction_type
                    == "unprocessed wallet withdrawal",
                    models.WalletTransaction.transaction_completed == False,
                    models.WalletTransaction.transaction_code
                    == originator_conversation_id,
                    models.WalletTransaction.destination == phone_number,
                    models.WalletTransaction.amount == result_dict["TransactionAmount"],
                    func.date(models.WalletTransaction.transaction_date) == today,
                )
            )
            .first()
        )

        if not unprocessed_withdrawal:
            db.rollback()
            raise HTTPException(
                status_code=404, detail="Unprocessed withdrawal transaction not found"
            )

        # update user's wallet balance
        user = (
            db.query(models.User)
            .filter(models.User.id == unprocessed_withdrawal.user_id)
            .with_for_update()
            .first()
        )

        if not user:
            db.rollback()
            raise HTTPException(status_code=404, detail="User not found")

        chamazetu_fees = (
            db.query(models.ChamazetuToMpesaFees)
            .filter(
                models.ChamazetuToMpesaFees.from_amount
                <= result_dict["TransactionAmount"]
            )
            .filter(
                models.ChamazetuToMpesaFees.to_amount
                >= result_dict["TransactionAmount"]
            )
            .first()
        )

        if not chamazetu_fees:
            db.rollback()
            raise HTTPException(status_code=404, detail="Fee not found")

        user.wallet_balance -= (
            result_dict["TransactionAmount"] + chamazetu_fees.chamazetu_to_mpesa
        )

        # update the transaction status to processed as sent since its completed transaction
        unprocessed_withdrawal.transaction_completed = True
        unprocessed_withdrawal.transaction_type = "sent"
        unprocessed_withdrawal.transaction_code = result_dict["TransactionReceipt"]
        unprocessed_withdrawal.transaction_date = completion_date

        # record the transaction in the B2CResults table
        new_result = models.B2CResults(
            originatorconversationid=originator_conversation_id,
            conversationid=result.get("Result", {}).get("OriginatorConversationID", ""),
            transactionid=result.get("Result", {}).get("TransactionID", ""),
            resulttype=result.get("Result", {}).get("ResultType", ""),
            resultcode=result.get("Result", {}).get("ResultCode", ""),
            resultdesc=result.get("Result", {}).get("ResultDesc", ""),
            transactionamount=result_dict["TransactionAmount"],
            transactionreceipt=result_dict["TransactionReceipt"],
            receiverpartypublicname=result_dict["ReceiverPartyPublicName"],
            transactioncompleteddatetime=completion_date,
            b2cutilityaccountavailablefunds=result_dict[
                "B2CUtilityAccountAvailableFunds"
            ],
            b2cworkingaccountavailablefunds=result_dict[
                "B2CWorkingAccountAvailableFunds"
            ],
            b2crecipientisregisteredcustomer=result_dict[
                "B2CRecipientIsRegisteredCustomer"
            ],
            b2cchargespaidaccountavailablefunds=result_dict[
                "B2CChargesPaidAccountAvailableFunds"
            ],
        )
        db.bulk_save_objects([new_result])

        if result_dict["TransactionAmount"] <= 100:
            db.commit()
            return {"message": "Transaction processed successfully."}

        # calculate rewards coins
        # print("===fee difference:", chamazetu_fees.difference)
        fee_difference = chamazetu_fees.difference
        # calculate the reward coins at 1 shilling = 2.5 coins
        reward_coins = fee_difference * 2.5
        # print("===reward coins:", reward_coins)
        # cost of issued coins while redemption is at 10 coins = 1 shilling
        cost_of_issued_coins = reward_coins * 0.1
        # print("===cost of issued coins:", cost_of_issued_coins)
        # net charge after rewarding the user
        net_charge = fee_difference - cost_of_issued_coins
        # print("===net charge:", net_charge)
        # update the user's reward coins - zetucoins
        user.zetucoins += int(reward_coins)
        # print("===user's reward coins:", user.zetucoins)

        # update chamazetu's reward coins
        chamazetu = (
            db.query(models.ChamaZetu)
            .filter(models.ChamaZetu.id == 1)
            .with_for_update()
            .first()
        )
        chamazetu.withdrawal_fees += net_charge
        # how much shillings is the reward coins worth
        chamazetu.reward_coins += cost_of_issued_coins

        db.commit()
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to update transaction\n: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")


@celery_app.task
def complete_unprocessed_deposit(result: dict):
    db: Session = next(database.get_db())

    try:
        # user_id and unprocessed_code
        user_id, unprocessed_code = result['Result']['ReferenceData']['ReferenceItem']['Value'].split('/')
        # extract phone number
        phone_number = result['Result']['ResultParameters']['ResultParameter'][0]['Value'].split(' ')[0]

        if len(phone_number) == 10:
            phone_number = f"254{phone_number[1:]}"

        # extract amount
        amount = int(result['Result']['ResultParameters']['ResultParameter'][-3]['Value'])

        # extract transaction result code
        result_code = result['Result']['ResultCode']

        if result_code == 0:
            # update the wallet balance
            user_id = int(user_id)
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            user.wallet_balance += amount
            db.add(user)

            # update the transaction status
            unprocessed_transaction = (
                db.query(models.WalletTransaction)
                .filter(
                    and_(
                        models.WalletTransaction.amount == amount,
                        models.WalletTransaction.transaction_code == unprocessed_code,
                        models.WalletTransaction.user_id == user_id,
                        models.WalletTransaction.transaction_completed == False,
                        models.WalletTransaction.origin == phone_number,
                        )
                        )
                        .first()
                        )

            if not unprocessed_transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")

            unprocessed_transaction.transaction_completed = True
            unprocessed_transaction.transaction_code = result['Result']['ResultParameters']['ResultParameter'][-1]['Value']
            unprocessed_transaction.transaction_type = "deposit"
            db.add(unprocessed_transaction)

            db.commit()
            return {"message": "Transaction updated successfully."}
        else:
            raise HTTPException(status_code=400, detail="Failed to update transaction status.")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to update transaction\n: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@celery_app.task
def initiaite_final_fines_transfer_to_manager_wallet(activity_id: int, collected_fines:int, manager_id: int):
    db: Session = next(database.get_db())

    try:
        today = datetime.now(nairobi_tz).date()
        chama_activity = chamaActivity(db, activity_id)
        activity = chama_activity.activity()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")


        # begin transaction block for atomicity
        with db.begin_nested():
            # record the fines transfer
            db.add(models.ManagerFinesTranser(
                manager_id = manager_id,
                activity_id = activity_id,
                amount = collected_fines,
                transfer_date = today,
                current_cycle = chama_activity.current_activity_cycle()
            ))


            # update the manager's wallet balance
            manager_wallet = (
                db.query(models.User)
                .filter(models.User.id == manager_id)
                .with_for_update()
                .first()
            )

            if not manager_wallet:
                raise HTTPException(status_code=404, detail="Manager not found")

            manager_wallet.wallet_balance += collected_fines

            # update the activity account balance
            activity_account = (
                db.query(models.Activity_Account)
                .filter(models.Activity_Account.activity_id == activity_id)
                .with_for_update()
                .first()
            )

            if not activity_account:
                raise HTTPException(status_code=404, detail="Activity account not found")

            activity_account.account_balance -= collected_fines

            # update the chama account balance
            chama_account = (
                db.query(models.Chama_Account)
                .filter(models.Chama_Account.chama_id == activity.chama_id)
                .with_for_update()
                .first()
            )

            if not chama_account:
                raise HTTPException(status_code=404, detail="Chama account not found")

            chama_account.account_balance -= collected_fines

        db.commit()

        return {"message": "Fines transferred successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        db.rollback()
        management_error_logger.error(f"Failed to transfer fines, error: {exc}")
        raise HTTPException(status_code=400, detail="Failed to transfer fines")