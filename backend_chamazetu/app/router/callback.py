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


from .. import schemas, database, utils, oauth2, models
from .stk_push import stk_push_status, generate_access_token, generate_password

router = APIRouter(prefix="/callback", tags=["callback"])

transaction_info_logger = logging.getLogger("transactions_info")
transaction_error_logger = logging.getLogger("transactions_error")

nairobi_tz = ZoneInfo("Africa/Nairobi")


# transaction status function
async def check_transaction_status(transaction_id: str) -> dict:
    url = os.getenv("TRANSACTION_STATUS_URL")
    access_token = await generate_access_token()
    password, timestamp = generate_password()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    payload = {
        "Initiator": "BLACKALPHA NJOROGE VENTURES",
        "SecurityCredential": password,
        "CommandID": "TransactionStatusQuery",
        "TransactionID": transaction_id,
        "PartyA": 4138859,
        "IdentifierType": "4",
        "ResultURL": "https://chamazetu.com/TransactionStatus/result",
        "QueueTimeOutURL": "https://chamazetu.com/TransactionStatus/queue",
        "Remarks": "Transaction status query",
        "Occasion": "Updating call back data table",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()

    return response_data


@router.post("/data", status_code=status.HTTP_201_CREATED)
async def callback_data(
    transaction_data: schemas.MpesaResponse = Body(...),
    db: Session = Depends(database.get_db),
):
    try:
        transaction_date = datetime.strptime(
            str(transaction_data.TransactionDate), "%Y%m%d%H%M%S"
        )

        # Store the data in the callback table
        new_callback = models.CallbackData(
            MerchantRequestID=transaction_data.MerchantRequestID,
            CheckoutRequestID=transaction_data.CheckoutRequestID,
            ResultCode=transaction_data.ResultCode,
            ResultDesc=transaction_data.ResultDesc,
            Amount=transaction_data.Amount,
            MpesaReceiptNumber=transaction_data.MpesaReceiptNumber,
            TransactionDate=transaction_date,
            PhoneNumber=transaction_data.PhoneNumber,
            Purpose="wallet",
            Status="Pending",
        )
        db.add(new_callback)

        # Commit the transaction
        db.commit()
        db.refresh(new_callback)

    except Exception as e:
        print(e)
        # Rollback the transaction in case of an error
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the transaction.",
        )

    finally:
        # Close the session
        db.close()

    return {"message": "Transaction processed successfully."}


@router.put(
    "/update_pending_callback_data/{checkoutid}", status_code=status.HTTP_200_OK
)
async def update_pending_callback_data(
    checkoutid: str,
    db: Session = Depends(database.get_db),
):

    try:
        # Retrieve the callback data for the given checkout id with a lock for update
        callback_data = (
            db.query(models.CallbackData)
            .filter(models.CallbackData.CheckoutRequestID == checkoutid)
            .with_for_update()
            .first()
        )

        if not callback_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Callback data not found.",
            )

        # Update the status of the callback data to success
        callback_data.Status = "Success"
        db.commit()  # Commit the transaction
    except SQLAlchemyError as e:
        db.rollback()  # Rollback the transaction in case of an error
        transaction_error_logger.error(f"Failed to update callback data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Callback data updated successfully."}


@router.put("/update_callback_transactions", status_code=status.HTTP_200_OK)
async def update_callback_transactions(
    db: Session = Depends(database.get_db),
):
    transaction_info_logger.info("Updating callback transactions")
    try:
        kenya_tz = ZoneInfo("Africa/Nairobi")
        five_minutes_ago = datetime.now(kenya_tz) - timedelta(minutes=5)

        # Retrieve all pending callback transactions
        pending_transactions = (
            db.query(models.CallbackData)
            .filter(models.CallbackData.Status == "Pending")
            .filter(models.CallbackData.TransactionDate <= five_minutes_ago)
            .all()
        )

        if pending_transactions:
            transaction_info_logger.info("Updating callback transactions")
            transaction_info_logger.info(
                f"Transactions to update: {len(pending_transactions)}"
            )
            for transaction in pending_transactions:
                transaction_info_logger.info(
                    f"Updating transaction: {transaction.MpesaReceiptNumber}"
                )
                transaction_id = transaction.MpesaReceiptNumber

                # Call the stk_push_status function directly
                response = await check_transaction_status(transaction_id)
                transaction_info_logger.info(f"Response: {response}")

                if response["ResponseCode"] == "0":
                    # Update transaction status to success
                    transaction.Status = "Success"
                else:
                    # Update transaction status to failed with reason
                    transaction.Status = "Failed"
                    transaction.ResultDesc = response["ResponseDescription"]
                    transaction.ResultCode = response["ResponseCode"]

                db.add(transaction)

            db.commit()
        return {"message": "Callback transactions updated successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        # Handle any other exceptions
        db.rollback()
        transaction_error_logger.error(
            f"Failed to update callback transactions: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e))


# if a user  deposits to mpesa and the amount doesn't reflect in the wallet, we can update that if they provide the transaction code
@router.put(
    "/fix_unprocessed_deposit/{transaction_code}/{receipt_number}",
    status_code=status.HTTP_200_OK,
)
async def fix_unprocessed_deposit(
    transaction_code: str,
    receipt_number: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):

    try:
        user = db.query(models.User).filter(models.User.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # Retrieve the transaction
        transaction = (
            db.query(models.WalletTransaction)
            .filter(models.WalletTransaction.transaction_code == transaction_code)
            .first()
        )

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )

        # check the status of the transaction using the receipt number
        response = await check_transaction_status(receipt_number)
        transaction_info_logger.info(f"Response: {response}")

        if response["ResponseCode"] == "0":
            # Update transaction status to success
            transaction.transaction_completed = True
            transaction.transaction_code = receipt_number
            transaction.transaction_type = "deposit"

            # update the wallet balance
            user.wallet_balance += transaction.amount

            db.add(transaction)
            db.add(user)
            db.commit()
        else:
            transaction_error_logger.error(f"Failed to update transaction: {response}")
            raise HTTPException(
                status_code=400, detail="Failed to update transaction status."
            )

        return {"message": "Transaction updated successfully."}
    except HTTPException as http_exc:
        transaction_error_logger.error(f"Failed to update transaction: {str(http_exc)}")
        db.rollback()
        raise http_exc
    except Exception as e:
        # Handle any other exceptions
        db.rollback()
        transaction_error_logger.error(f"Failed to update transaction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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


@router.post("/b2c/result", status_code=status.HTTP_201_CREATED)
async def b2c_result(result: dict, db: Session = Depends(database.get_db)):
    try:
        print("=====b2c result=====")
        print(result)
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

        # TODO: remember to minus the transaction charges from the wallet balance as well
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
        print("===fee difference:", chamazetu_fees.difference)
        fee_difference = chamazetu_fees.difference
        # calculate the reward coins at 1 shilling = 2.5 coins
        reward_coins = fee_difference * 2.5
        print("===reward coins:", reward_coins)
        # cost of issued coins while redemption is at 10 coins = 1 shilling
        cost_of_issued_coins = reward_coins * 0.1
        print("===cost of issued coins:", cost_of_issued_coins)
        # net charge after rewarding the user
        net_charge = fee_difference - cost_of_issued_coins
        print("===net charge:", net_charge)
        # update the user's reward coins - zetucoins
        user.zetucoins += int(reward_coins)
        print("===user's reward coins:", user.zetucoins)

        # update chamazetu's reward coins
        chamazetu = (
            db.query(models.ChamaZetu)
            .filter(models.ChamaZetu.id == 1)
            .with_for_update()
            .first()
        )
        chamazetu.withdrawal_fees += net_charge
        print("===chamazetu's withdrawal fees:", chamazetu.withdrawal_fees)
        # how much shillings is the reward coins worth
        chamazetu.reward_coins += cost_of_issued_coins

        db.commit()
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to update transaction\n: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")


@router.post("/b2c/queue", status_code=status.HTTP_201_CREATED)
async def b2c_queue(timeout: dict):
    print("=====b2c timeout=====")
    print(timeout)
    transaction_error_logger.error(f"Failed to update transaction\n: {timeout}")
    return {"message": "B2C timeout processed successfully."}


@router.post("/c2b/{unprocessed_code}", status_code=status.HTTP_201_CREATED)
async def c2b_callback(
    unprocessed_code: str,
    transaction_data: dict,
    db: Session = Depends(database.get_db),
):
    try:
        print("======c2b callback=====")
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
        transaction_date = datetime.strptime(
            str(
                transaction_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"][3][
                    "Value"
                ]
            ),
            "%Y%m%d%H%M%S",
        )
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
    except Exception as e:
        db.rollback()
        transaction_error_logger.error(f"Failed to update transaction\n: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")


# a better registration callback
@router.post("/registration/{unprocessed_code}", status_code=status.HTTP_201_CREATED)
async def chama_registration(
    unprocessed_code: str,
    registration_data: dict,
    db: Session = Depends(database.get_db),
):

    try:
        print("====regi data=====")
        print(registration_data)

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
