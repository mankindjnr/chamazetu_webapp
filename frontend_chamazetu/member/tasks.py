from __future__ import absolute_import, unicode_literals
from celery import shared_task, current_task
import requests, os, time, logging
from datetime import datetime, timedelta
from celery.exceptions import MaxRetriesExceededError
from dotenv import load_dotenv
from django.conf import settings
from django.template.loader import render_to_string
from http import HTTPStatus
from zoneinfo import ZoneInfo

from .members import (
    get_wallet_balance,
    get_member_expected_contribution,
    get_member_contribution_so_far,
    get_user_email,
    get_user_full_name,
)

from chama.tasks import sending_email

load_dotenv()

logger = logging.getLogger("member")

nairobi_tz = ZoneInfo("Africa/Nairobi")


@shared_task
def date_time_log_member():
    logger.info("==========member/tasks.py: log_date_time()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    # date
    logger.info(f"Date: {datetime.now().date()}")
    # time
    logger.info(f"Time: {datetime.now().time()}")
    # nairobi
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")

    return None


@shared_task
def update_chama_account_balance(chama_id, amount, transaction_type):
    url = f"{os.getenv('api_url')}/chamas/update_account"

    data = {
        "chama_id": chama_id,
        "amount_deposited": amount,
        "transaction_type": transaction_type,
    }

    response = requests.put(url, json=data)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to update chama account balance: {response.status_code}, {response.text}"
        )
    return None


@shared_task
def update_shares_number_for_member(chama_id, num_of_shares, headers):
    url = f"{os.getenv('api_url')}/chamas/update_shares"

    data = {
        "chama_id": chama_id,
        "num_of_shares": num_of_shares,
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to update member shares: {response.status_code}, {response.text}"
        )
    return None


@shared_task
def update_wallet_balance(
    headers, amount, chama_id, transaction_type, transaction_code
):
    url = f"{os.getenv('api_url')}/members/update_wallet_balance"

    if (
        transaction_type == "moved_to_wallet"
        or transaction_type == "deposited_to_wallet"
    ):
        transaction_destination = 0  # default value for wallet
    elif (
        transaction_type == "withdrawn_from_wallet"
        or transaction_type == "moved_to_chama"
    ):
        transaction_destination = chama_id

    data = {
        "transaction_destination": int(transaction_destination),
        "amount": int(amount),
        "transaction_type": transaction_type,
        "transaction_code": transaction_code,
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to update wallet balance: {response.status_code}, {response.text}"
        )
    return None


@shared_task
def wallet_deposit(mpesa_data):
    if not mpesa_data:
        return
    headers = mpesa_data["headers"]
    amount = mpesa_data["amount"]
    member_id = mpesa_data["member_id"]
    transaction_code = mpesa_data["checkoutrequestid"]

    url = f"{os.getenv('api_url')}/members/update_wallet_balance"

    data = {
        "transaction_destination": 0,
        "amount": amount,
        "transaction_type": "deposited_to_wallet",
        "transaction_code": transaction_code,
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to deposit to wallet: {response.status_code}, {response.text}"
        )
    return None


# TODO: this is a business to customer transaction
@shared_task
def wallet_withdrawal(headers, amount, member_id, transaction_code):
    url = f"{os.getenv('api_url')}/members/update_wallet_balance"

    data = {
        "transaction_destination": 0,  # should be the phone number of the member, where the money is being withdrawn to
        "amount": amount,
        "transaction_type": "withdrawn_from_wallet",
        "transaction_code": transaction_code,
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to withdraw from wallet: {response.status_code}, {response.text}"
        )
    return None


@shared_task
def update_users_profile_image(headers, role, new_profile_image_name):
    url = f"{os.getenv('api_url')}/bucket-uploads/{role}/update_profile_picture"

    data = {
        "profile_picture_name": new_profile_image_name,
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to update profile picture: {response.status_code}, {response.text}"
        )
    return None


@shared_task(bind=True, max_retries=3)
def stk_push_status(
    self,
    checkoutrequestid,
    member_id,
    destination,  # chama_id or wallet
    amount,
    phone_number,
    transaction_origin,
    headers,
):
    """
    Check the status of the stk push
    """
    time.sleep(60)
    for _ in range(3):
        try:
            response = requests.get(
                f"{os.getenv('api_url')}/request/status/{checkoutrequestid}",
            )
            print("=====first phone number====")
            print(phone_number)
            if response.status_code == 200:
                if response.json()["queryResponse"]["ResultCode"] == "0":
                    successful_push_data = {
                        "checkoutrequestid": checkoutrequestid,
                        "member_id": member_id,
                        "destination": destination,
                        "amount": amount,
                        "phone_number": phone_number,
                        "transaction_origin": transaction_origin,
                        "headers": headers,
                    }
                    return successful_push_data
                else:
                    return None
            else:
                time.sleep(30)
        except Exception as e:
            try:
                self.retry(exc=e, countdown=30)
            except MaxRetriesExceededError:
                raise Exception("Max retries exceeded")


@shared_task
def after_succesful_chama_deposit(mpesa_data):
    """
    After a successful stk push we add the amount to the chama account, update wallets if necessary
    """
    if not mpesa_data:
        return
    member_id = mpesa_data["member_id"]
    chama_id = mpesa_data["destination"]
    amount = mpesa_data["amount"]
    phone_number = mpesa_data["phone_number"]
    transaction_origin = mpesa_data["transaction_origin"]
    transaction_code = mpesa_data["checkoutrequestid"]
    headers = mpesa_data["headers"]

    # TODO: check for fines and update amount onwards but exit only after updaing account balance:
    # return amount after paying fines
    print("=====second phone number====")
    print(phone_number)
    print("=======checking for fines====")
    print("===", amount, "===")
    if member_has_fines_or_missed_contributions(member_id, chama_id):
        print("=======member has fines====")
        # =======checking if member has fines before calling the fine repayment function====
        amount = balance_after_paying_fines_and_missed_contributions(
            headers, amount, member_id, chama_id, transaction_code, phone_number
        )
        print("=======amount after fines====")
        print(amount, "===")

    print("=======checking for fines done====")
    print("===:", amount)
    if amount > 0:
        print("------amount > 0---------")
        expected_difference = difference_btwn_contributed_and_expected(
            member_id, chama_id
        )
        if expected_difference == 0:
            print("=======in expected difference == 0====")
            update_wallet_balance.delay(
                headers, amount, chama_id, "moved_to_wallet", transaction_code
            )
            # "Excess amount of Ksh: {amount} deposited to wallet. You have already contributed the expected amount for this contribution interval."
            return

        if deposit_is_greater_than_difference(amount, member_id, chama_id):
            print("=======in deposit_is_greater_than_difference====")
            excess_amount = amount - expected_difference
            amount_to_deposit = expected_difference
            update_wallet_balance.delay(
                headers, excess_amount, chama_id, "moved_to_wallet", transaction_code
            )
            # "Excess amount of Ksh: {excess_amount} deposited to wallet.",

            amount = amount_to_deposit

        # deposit the amount to chama
        url = f"{os.getenv('api_url')}/transactions/direct_deposit"
        data = {
            "amount": amount,
            "member_id": member_id,
            "chama_id": chama_id,
            "phone_number": f"254{phone_number}",
            "transaction_origin": transaction_origin,
            "transaction_code": transaction_code,
        }

        for _ in range(3):
            response = requests.post(url, json=data)
            if response.status_code == HTTPStatus.CREATED:
                print("=======deposit successful update====")
                # call the background task function to update the chama account balance
                update_chama_account_balance.delay(chama_id, amount, "deposit")
                # "Deposit of Khs: {amount} to {request.POST.get('chamaname')} successful",
                return
            else:
                time.sleep(30)
    print("=======amount < 0====")
    return


def difference_btwn_contributed_and_expected(member_id, chama_id):
    # get the amount expected
    amount_expected = get_member_expected_contribution(member_id, chama_id)
    # get the amount contributed so far
    amount_contributed_so_far = get_member_contribution_so_far(chama_id, member_id)
    expected_difference = amount_expected - amount_contributed_so_far
    if expected_difference < 0:
        return 0

    return expected_difference


def deposit_is_greater_than_difference(deposited, member_id, chama_id):
    return int(deposited) > difference_btwn_contributed_and_expected(
        member_id, chama_id
    )


# retrieve chamas share price, previous contribution day and one before that
@shared_task
def calculate_missed_contributions_fines():
    logger.info("==========member/tasks.py: calculate_missed_contributions_fines()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Date: {datetime.now(nairobi_tz)}")
    url = f"{os.getenv('api_url')}/members/share_price_and_prev_two_contribution_dates"
    response = requests.get(url)

    data = response.json()
    url = f"{os.getenv('api_url')}/members/members_and_contribution_fines"
    requests.get(url, json=data)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to calculate missed contributions and fines: {response.status_code}, {response.text}"
        )

    return None


# balance after repaying fines and missed contributions
def balance_after_paying_fines_and_missed_contributions(
    headers, amount, member_id, chama_id, transaction_code, phone_number
):

    # we first move the money from the wallet to the chama if its a success we continue with the repayment
    url = f"{os.getenv('api_url')}/transactions/record_fine_payment_from_mpesa"
    data = {
        "amount": amount,
        "transaction_destination": chama_id,
        "phone_number": f"254{phone_number}",
        "transaction_code": transaction_code,
        "member_id": member_id,
    }

    repayment_response = requests.post(url, json=data)
    if repayment_response.status_code == HTTPStatus.CREATED:
        url = f"{os.getenv('api_url')}/members/repay_fines"
        data = {
            "member_id": member_id,
            "chama_id": chama_id,
            "amount": amount,
        }

        resp = requests.put(url, json=data)

        # using the received amount and balance_after - update wallet, transaction and accout - bg task

        if resp.status_code == HTTPStatus.OK:
            print("======repaying done========")
            paid_fine = amount - resp.json().get("balance_after_fines")
            print(paid_fine)
            update_chama_account_balance.delay(chama_id, paid_fine, "deposit")
            return resp.json().get("balance_after_fines")
        else:
            return amount
    else:
        # if the wallet deposit fails, we return the amount to the user to try and deposit again by killing the transaction
        # "Failed to deposit Ksh: {amount} to {chama_name}. Please try again later."
        # TODO: fix this, handle the error better
        return amount


def member_has_fines_or_missed_contributions(member_id, chama_id):
    print("====checking for members fines=====")
    url = f"{os.getenv('api_url')}/members/fines"
    data = {"member_id": member_id, "chama_id": chama_id}
    resp = requests.get(url, json=data)
    if resp.status_code == HTTPStatus.OK:
        has_fines = resp.json().get("has_fines")
        print("=======has====")
        print(has_fines)
        return has_fines
    return False


# check on the status of the registration fee payment
def registration_fee_status(
    checkoutrequestid,
):
    time.sleep(60)
    for _ in range(3):
        try:
            response = requests.get(
                f"{os.getenv('api_url')}/request/status/{checkoutrequestid}",
            )
            if response.status_code == HTTPStatus.OK:
                if response.json()["queryResponse"]["ResultCode"] == "0":
                    return True
                else:
                    return False
            else:
                time.sleep(30)
        except Exception as e:
            try:
                self.retry(exc=e, countdown=30)
            except MaxRetriesExceededError:
                raise Exception("Max retries exceeded")


# this will call the backend with member data to add them to chama if the payment is successful
@shared_task(bind=True, max_retries=3, default_retry_delay=40)
def add_member_to_chama(
    self, chama_id, member_id, num_of_shares, registration_fee, checkoutid
):
    try:
        if registration_fee_status(checkoutid):
            # call a bg task to update the call back data from pending to success
            update_pending_callback_data.delay(checkoutid)
            # call the backend to add the member to the chama
            url = f"{os.getenv('api_url')}/chamas/join"
            data = {
                "chama_id": chama_id,
                "member_id": member_id,
                "num_of_shares": num_of_shares,
            }

            response = requests.post(url, json=data)
            if response.status_code == HTTPStatus.CREATED:
                pass
                # send_email_to_new_member(member_id, chama_id) - to the member login page
                send_email_to_new_chama_member.delay(member_id, chama_id)
                # bg task to deposit the registration fee to the chama account minus 9.4% transaction fee
                # TODO: call another bg task to update chamazetu accounts with the 9.4% transaction fee - business account
                amount = registration_fee - (0.094 * registration_fee)
                update_chama_account_balance.delay(chama_id, amount, "deposit")
            else:
                # if the request was unsuccessful, retry the task
                raise Exception("Failed to add member to chama")
    except Exception as e:
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            raise Exception("Max retries exceeded")


@shared_task
def update_pending_callback_data(checkoutid):
    url = f"{os.getenv('api_url')}/callback/update_pending_callback_data/{checkoutid}"
    response = requests.put(url)
    return None


@shared_task
def send_email_to_new_chama_member(member_id, chama_id):
    email = get_user_email("member", member_id)
    user_name = get_user_full_name("member", member_id)
    if email:
        direct_to_page = "https://chamazetu.com/signin/member"
        mail_subject = "You have successfully joined a chama"
        message = render_to_string(
            "chama/joinedChamaSuccess.html",
            {
                "user": email,
                "user_name": user_name,
                "go_to_page": direct_to_page,
            },
        )

        from_email = settings.EMAIL_HOST_USER
        to_email = [email]

        sending_email.delay(mail_subject, message, from_email, to_email)
    return None
