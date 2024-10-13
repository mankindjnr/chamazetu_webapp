from __future__ import absolute_import, unicode_literals
from celery import shared_task, current_task
import requests, os, time, logging
from datetime import datetime, timedelta
from celery.exceptions import MaxRetriesExceededError
from dotenv import load_dotenv
from django.conf import settings
from django.template.loader import render_to_string
from http import HTTPStatus
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    RetryError,
)
from zoneinfo import ZoneInfo

from .members import (
    get_wallet_balance,
    get_member_expected_contribution,
    get_member_contribution_so_far,
    get_user_email,
    get_user_full_name,
    get_member_wallet_number,
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
    member_id, amount, chama_id, transaction_type, transaction_code
):
    url = f"{os.getenv('api_url')}/members/update_wallet_balance"

    if (
        transaction_type == "moved_to_wallet"
        or transaction_type == "deposited_to_wallet"
    ):
        transaction_destination = get_member_wallet_number(member_id)
    elif (
        transaction_type == "withdrawn_from_wallet"
        or transaction_type == "moved_to_chama"
    ):
        transaction_destination = chama_id

    data = {
        "member_id": member_id,
        "transaction_destination": transaction_destination,
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


# TODO: this is a business to customer transaction
@shared_task
def wallet_withdrawal(headers, amount, member_id, transaction_code):
    url = f"{os.getenv('api_url')}/members/update_wallet_balance"

    data = {
        "member_id": member_id,
        "transaction_destination": 0,  # should be the phone number of the member, where the money is being withdrawn to
        "amount": amount,
        "transaction_type": "withdrawn_from_wallet",
        "transaction_code": transaction_code,
    }

    response = requests.put(url, json=data)
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to withdraw from wallet: {response.status_code}, {response.text}"
        )
    return None


@shared_task
def update_users_profile_image(headers, new_profile_image_name):
    url = f"{os.getenv('api_url')}/bucket-uploads/update_profile_picture"

    data = {
        "profile_picture_name": new_profile_image_name,
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code == HTTPStatus.OK:
        return True
    else:
        logger.error(
            f"Failed to update profile picture: {response.status_code}, {response.text}"
        )
    return None


@shared_task(bind=True)
def mpesa_request(
    self, amount, checkoutrequestid, user_id, phonenumber, destination, transaction_code
):
    max_retries = 3
    delay_before_check = 13  # first try after 13 seconds
    retry_delay = 5  # retry after 5 seconds

    # wait a few seconds to allow the mpesa to process the request
    time.sleep(delay_before_check)

    for attempt in range(1, max_retries + 1):
        try:
            # check te status
            status_url = f"{os.getenv('api_url')}/request/status/{checkoutrequestid}"
            response = requests.get(status_url)

            if response.status_code == HTTPStatus.OK:
                print("=======\n", response.json(), "\n========")
                query_response = response.json()
                print("=========\n", query_response, "\n=========")

                # if the stk push was a success
                if query_response.get("ResultCode") == "0":
                    print("stk push was successful")

                    load_wallet = requests.put(
                        f"{os.getenv('api_url')}/transactions/load_wallet",
                        json={
                            "amount": amount,
                            "unprocessed_code": transaction_code,
                            "wallet_id": destination,
                            "transaction_origin": phonenumber,
                            "transaction_code": checkoutrequestid,
                            "user_id": user_id,
                        },
                    )

                    if load_wallet.status_code == HTTPStatus.OK:
                        print("wallet loaded successfully")
                        return True
                    else:
                        print("failed to load wallet")
                        return False

                else:
                    print("stk push failed")
                    return False

            # if the request failed
            else:
                print("failed to check status")
                print(response.text)
                return False

        except Exception as e:
            print(f"failed to check status: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)

    return False


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
    since  we no longer do direct chama deposits, we will only make unprocessed deposits to the wallet
    or default to using the callback - we will update the callback table to success
    """

    time.sleep(60)

    retry_delay = 30  # initial retry delay
    for attempt in range(3):
        try:
            response = requests.get(
                f"{os.getenv('api_url')}/request/status/{checkoutrequestid}",
            )
            if response.status_code == HTTPStatus.OK:
                result_code = response.json()["queryResponse"]["ResultCode"]
                if result_code == "0":
                    successful_push_data = {
                        "checkoutrequestid": checkoutrequestid,
                        "member_id": member_id,
                        "destination": destination,
                        "amount": amount,
                        "phone_number": phone_number,
                        "transaction_origin": transaction_origin,
                    }
                    return successful_push_data
                else:
                    return {
                        "error": "Transaction not successful",
                        "result_code": result_code,
                    }
            else:
                logger.error(
                    f"Failed to check stk push status: {checkoutrequestid} {response.status_code}, {response.text}"
                )
                raise Exception("Failed to check stk push status")

        except Exception as e:
            if attempt < 2:
                time.sleep(retry_delay)
                retry_delay *= 2  # exponential backoff
            else:
                try:
                    self.retry(exc=e, countdown=retry_delay)
                except MaxRetriesExceededError:
                    raise Exception("Max retries exceeded") from e

    raise Exception("Max retries exceeded")


@shared_task
def wallet_deposit(mpesa_data):
    if not mpesa_data:
        return
    amount = mpesa_data["amount"]
    member_id = mpesa_data["member_id"]
    transaction_code = mpesa_data["checkoutrequestid"]

    url = f"{os.getenv('api_url')}/members/deposit_to_wallet"

    data = {
        "member_id": member_id,
        "transaction_destination": get_member_wallet_number(member_id),
        "amount": amount,
        "transaction_type": "deposit to wallet",
        "transaction_code": transaction_code,
    }

    response = requests.put(url, json=data)
    if response.status_code == HTTPStatus.OK:
        return True
    else:
        logger.error(
            f"Failed to deposit to wallet: {response.status_code}, {response.text}"
        )
    return None


# test a normal retry mechanism
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

    logger.info(f"amountb4:{amount}")
    if member_has_fines_or_missed_contributions(member_id, chama_id):
        # TODO: later we could just retrieve the amount to repay and make all transaction at once
        amount = balance_after_paying_fines_and_missed_contributions(
            headers, amount, member_id, chama_id, transaction_code, phone_number
        )
        logger.info(f"amountrepaid:{amount}")

    transaction_data = {
        "member_id": member_id,
        "chama_id": chama_id,
        "transaction_code": transaction_code,
        "wallet_update": None,
        "direct_deposit": None,
        "wallet_deposit": None,
    }
    if amount > 0:
        logger.info(f"greaterafter:{amount}")
        expected_difference = difference_btwn_contributed_and_expected(
            member_id, chama_id
        )
        if expected_difference == 0:
            # if all cont have been made then this amt will now move to wallet
            logger.info(f"wallet_deposit:{amount}")
            transaction_data["wallet_deposit"] = {
                "amount": amount,
                "transaction_type": "moved_to_wallet",
            }
        elif expected_difference > 0:  # we have contributions to make
            if deposit_is_greater_than_difference(amount, member_id, chama_id):
                # the deposit is greater than the expected difference
                # so we will deposit the expected difference and move excess to wallet
                excess_amount_to_wallet = amount - expected_difference
                amount_to_chama = expected_difference
                logger.info(
                    f"excess:{excess_amount_to_wallet} to chama:{amount_to_chama}"
                )
                transaction_data["wallet_update"] = {
                    "amount": excess_amount_to_wallet,
                    "transaction_type": "moved_to_wallet",
                }
                amount = amount_to_chama

        # deposit the expected amount to chama
        # would it be better if i decoupled the wallet deposit, the route  and also the data structure below.
        # if  wallet deposit alone, i could keep a the route but change the data structure delivrery.
        transaction_data["direct_deposit"] = {
            "amount": amount,
            "phone_number": f"254{phone_number}",
            "transaction_origin": transaction_origin,
        }

        # make the transaction together and update account balance with this amount
        logger.info(f"transaction_data:{transaction_data}")
        url = f"{os.getenv('api_url')}/transactions/unified_deposit_transactions"
        response = requests.post(url, json=transaction_data)

        if response.status_code == HTTPStatus.CREATED:
            return
        else:
            logger.error(f"Failed to record deposit transactions: {response.text}")
            raise Exception("Failed to record deposit transactions")


def member_has_fines_or_missed_contributions(member_id, chama_id):
    url = f"{os.getenv('api_url')}/members/fines"
    data = {"member_id": member_id, "chama_id": chama_id}
    resp = requests.get(url, json=data)
    if resp.status_code == HTTPStatus.OK:
        has_fines = resp.json().get("has_fines")
        return has_fines
    logger.error(
        f"Failed to check if member has fines: {resp.status_code}, {resp.text}"
    )
    return False


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
    logger.info(
        "==========member/tasks.py: calculate_missed_contributions_fines()=========="
    )
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    url = f"{os.getenv('api_url')}/members/share_price_and_prev_two_contribution_dates"
    response = requests.get(url)

    data = response.json()
    url = f"{os.getenv('api_url')}/members/setting_chama_members_contribution_fines"
    resp = requests.post(url, json=data)
    if resp.status_code == HTTPStatus.CREATED:
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
    url = f"{os.getenv('api_url')}/members/repay_fines_from_mpesa"
    data = {
        "transaction_code": transaction_code,
        "phone_number": f"254{phone_number}",
        "member_id": member_id,
        "chama_id": chama_id,
        "amount": amount,
    }

    resp = requests.put(url, json=data)

    # using the received amount and balance_after - update wallet, transaction and accout - bg task
    if resp.status_code == HTTPStatus.OK:
        return resp.json().get("balance_after_fines")
    else:
        return amount

    return amount


# check on the status of the registration fee payment
def registration_fee_status(checkoutrequestid):
    max_retries = 3
    delay_before_check = 10  # first try after 10 seconds
    retry_delay = 5  # retry after 5 seconds

    time.sleep(delay_before_check)

    for attempt in range(1, max_retries + 1):
        try:
            status_url = f"{os.getenv('api_url')}/request/status/{checkoutrequestid}"
            response = requests.get(status_url)

            if response.status_code == HTTPStatus.OK:
                query_response = response.json()
                if query_response.get("ResultCode") == "0":
                    return True
                else:
                    return False

            else:
                raise Exception("Failed to check status")

        except Exception as e:
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                raise Exception("Max retries exceeded")


# this will call the backend with member data to add them to chama if the payment is successful
@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def add_member_to_chama(
    self, chama_id, user_id, registration_fee, checkoutid, unprocessed_code
):
    try:
        if registration_fee_status(checkoutid):
            url = f"{os.getenv('api_url')}/chamas/become_a_chama_member"
            data = {
                "chama_id": chama_id,
                "user_id": user_id,
                "registration_fee": registration_fee,
                "unprocessed_code": unprocessed_code,
            }
            response = requests.post(url, json=data)
            if response.status_code == HTTPStatus.CREATED:
                send_email_to_new_chama_member.delay(user_id)
                return True
            else:
                raise Exception("Failed to add member to chama")
    except Exception as e:
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            raise Exception("Max retries exceeded")


@shared_task
def update_pending_registration_callback_data(checkoutid):
    url = f"{os.getenv('api_url')}/callback/update_pending_callback_data/{checkoutid}"
    response = requests.put(url)
    return None


@shared_task
def send_email_to_new_chama_member(user_id):
    email = get_user_email(user_id)
    user_name = get_user_full_name(user_id)
    if email:
        direct_to_page = "https://chamazetu.com/signin/"
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


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def auto_contribute():
    logger.info("==========member/tasks.py: auto_contribute()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(
        f"{os.getenv('api_url')}/members/make_activity_auto_contributions"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to auto contribute: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def merry_go_round_activity_auto_contributions(*args, **kwargs):
    """
    auto contributions for merry_go_round_activities
    """
    logger.info(
        "==========chama/tasks.py: merry_go_round_activity_auto_contributions()=========="
    )
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(
        f"{os.getenv('api_url')}/activities/automated_merry_go_round_contributions"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create rotating contributions: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


@shared_task
def make_auto_contributions():
    logger.info("==========member/tasks.py: make_auto_contributions()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    generic_auto = auto_contribute.s()
    merry_go_round_auto = merry_go_round_activity_auto_contributions.s()

    return chain(generic_auto | merry_go_round_auto)()


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def send_contribution_reminders():
    pass
