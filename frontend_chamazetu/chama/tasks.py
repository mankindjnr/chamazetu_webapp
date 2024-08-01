from __future__ import absolute_import, unicode_literals
from celery import shared_task, current_task, chain
from celery.exceptions import MaxRetriesExceededError
from django.core.mail import send_mail
import requests, os, time, logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
from http import HTTPStatus
from zoneinfo import ZoneInfo

from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib import messages
from frontend_chamazetu import settings

load_dotenv()

logger = logging.getLogger("chama")

nairobi_tz = ZoneInfo("Africa/Nairobi")


# log date and time of the task - hopefully we can know the timezone of the server
@shared_task
def chama_date_time_log():
    logger.info("==========chama/tasks.py: log_date_time()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    # date
    logger.info(f"Date: {datetime.now().date()}")
    # time
    logger.info(f"Time: {datetime.now().time()}")
    # nairobi
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")

    return None


@shared_task
def sending_email(subject, message, from_email, to_email):
    """
    Send an email to the user
    the [to_email] is the email of the user or the recipient list.
    """
    msg = EmailMultiAlternatives(subject, message, from_email, to_email)
    msg.attach_alternative(message, "text/html")
    msg.send(fail_silently=True)
    return None


@shared_task
def set_contribution_date(first_contribution_date, chama_name):
    """
    Set the first contribution date for the chama
    """

    # Convert datetime object to string in ISO 8601 format
    first_contribution_date = (
        first_contribution_date.isoformat()
        if isinstance(first_contribution_date, datetime)
        else first_contribution_date
    )

    response = requests.post(
        f"{os.getenv('api_url')}/chamas/set_first_contribution_date",
        json={
            "first_contribution_date": first_contribution_date,
            "chama_name": chama_name,
        },
    )
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to set first contribution date: {response.status_code}, {response.text}"
        )

    return None


# update the contribution days for the chamas
@shared_task
def update_contribution_days():
    """
    Update the next contribution day for chamas
    """
    logger.info("==========chama/tasks.py: update_contribution_days()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.put(f"{os.getenv('api_url')}/chamas/update_contribution_days")
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to update contribution days: {response.status_code}, {response.text}"
        )

    return None


@shared_task
def check_and_update_accepting_members_status():
    # TODO: we will be checking if today is past the last joining day, if it is we will update the chama to not accepting members
    pass


# calculate daily interests for the chamas
@shared_task
def calculate_daily_mmf_interests():
    """
    Calculate daily interests for the chamas
    """
    response = requests.put(
        f"{os.getenv('api_url')}/investments/chamas/calculate_daily_mmf_interests"
    )
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to calculate daily mmf interests: {response.status_code}, {response.text}"
        )

    return None


@shared_task
def reset_and_move_weekly_mmf_interests():
    """
    Reset and add weekly mmf interests to the principal
    """
    logger.info(f"=======chama/tasks.py: reset_and_move_weekly_mmf_interests()========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.put(
        f"{os.getenv('api_url')}/investments/chamas/reset_and_move_weekly_mmf_interest_to_principal"
    )
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to reset and move weekly mmf interests: {response.status_code}, {response.text}"
        )

    return None


@shared_task
def reset_monthly_mmf_interests():
    """
    Reset monthly mmf interests
    """
    response = requests.put(
        f"{os.getenv('api_url')}/investments/chamas/reset_monthly_mmf_interest"
    )
    if response.status_code == HTTPStatus.OK:
        return None
    else:
        logger.error(
            f"Failed to reset monthly mmf interests: {response.status_code}, {response.text}"
        )

    return None


# first chain task
# a task that will run once 12 hours, it checks on transactions in the callback table - if their status is
# pending, it will update them accordingly - check if the transaction has been processed and update - athe transactions shouldd have been made atleast 30 mins ago
@shared_task
def update_callback_transactions():
    """
    Update transactions in the callback table
    """
    logger.info("==========chama/tasks.py: update_callback_transactions()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    try:
        response = requests.put(
            f"{os.getenv('api_url')}/callback/update_callback_transactions"
        )
        if response.status_code == HTTPStatus.OK:
            return True
        else:
            logger.error(
                f"Failed to update callback transactions: {response.status_code}, {response.text}"
            )
    except requests.RequestException as e:
        logger.error(f"http req fialed: Failed to update callback transactions: {e}")

    return False


# route will check the transactions table and retrieve transactions whose  transaction type is "unprocessed deposit", it will then compare those transactions against
# the callback data table using the cehckout request id, if in the callback data that transaction is marked as success, we will reverse the amount to user.
@shared_task
def fix_callback_and_transactions_mismatch(*args, **kwargs):
    """
    Add missing transactions to the transactions table
    """
    logger.info(
        "==========chama/tasks.py: fix_callback_and_transactions_mismatch()=========="
    )
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    try:
        response = requests.put(
            f"{os.getenv('api_url')}/callback/fix_callback_transactions_table_mismatch"  # fix unprocessed transactions against the callback table
        )
        if response.status_code == HTTPStatus.OK:
            return None
        else:
            logger.error(
                f"Failed to add fixing transactions: {response.status_code}, {response.text}"
            )
    except requests.RequestException as e:
        logger.error(f"http req fialed: Failed to fix callback transactions: {e}")

    return False


@shared_task
def run_update_and_fix_callbacks():
    """
    Run update_callback_transactions and then fix_callback_and_transactions_mismatch if the first task is successful
    """
    update_task = update_callback_transactions.s()
    fix_task = fix_callback_and_transactions_mismatch.s()
    return chain(update_task | fix_task)()
