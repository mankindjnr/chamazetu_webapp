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


# call a route that will send sms to the user
@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def contribution_day_sms_notifications():
    """
    Send sms notifications to users on their contribution days
    """
    logger.info(
        "==========chama/tasks.py: contribution_day_sms_notifications()=========="
    )
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(
        f"{os.getenv('api_url')}/activities/contribution_day_sms_notifications"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send sms notifications: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


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
def send_email_invites(email_list, invite_to, name, html_content, text_content):
    subject = f"Invitation to join {invite_to} {name} at chamaZetu"
    from_email = os.getenv("EMAIL_HOST_USER")

    for email in email_list:
        to_email = [email]
        msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        msg.attach_alternative(html_content, "text/html")
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
            return True
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


# runs five minutes after midnight every day to check for chamas whose last joining has passed
# and update the chama to not accepting members
@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def check_and_update_accepting_members_status():
    """
    Check and update accepting members status
    """
    logger.info(
        "==========chama/tasks.py: check_and_update_accepting_members_status()=========="
    )
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.put(
        f"{os.getenv('api_url')}/chamas/check_and_update_accepting_members_status"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to check and update accepting members status: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.OK


# update the contribution days for chama activities
@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def update_activities_contribution_days(*args, **kwargs):
    """
    Update the next contribution day for chamas
    """
    logger.info("==========chama/tasks.py: update_contribution_days()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.put(
        f"{os.getenv('api_url')}/activities/update_contribution_days"
    )

    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to update contribution days: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.OK


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def set_fines_for_missed_contributions():
    """
    Set fines for late contributions
    """
    logger.info(
        "==========chama/tasks.py: set_fines_for_missed_contributions()=========="
    )
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(
        f"{os.getenv('api_url')}/activities/set_fines_for_missed_contributions"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to set fines for missed contributions: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def create_rotation_contributions(*args, **kwargs):
    """
    Create rotating contributions for chamas
    """
    logger.info("==========chama/tasks.py: create_rotating_contributions()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(
        f"{os.getenv('api_url')}/activities/create_rotation_contributions"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create rotating contributions: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def create_activity_rotation_contributions(activity_id):
    """
    Create rotating contributions for chamas
    """
    logger.info(
        "==========chama/tasks.py: create_activity_rotation_contributions()=========="
    )
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(
        f"{os.getenv('api_url')}/activities/create_activity_rotation_contributions/{activity_id}"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create rotating contributions: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def activity_auto_dibursement(*args, **kwargs):
    """
    Create rotating contributions for chamas
    """
    logger.info("==========chama/tasks.py: activity_auto_dibursement()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(f"{os.getenv('api_url')}/activities/auto_dibursement")
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create rotating contributions: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
)
def auto_disburse_to_walletts(*args, **kwargs):
    logger.info("==========member/tasks.py: auto_disburse_to_walletts()==========")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    response = requests.post(
        f"{os.getenv('api_url')}/managers/auto_disburse_to_wallets"
    )
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to auto disburse to wallets: {e}")
        raise self.retry(exc=e)

    return response.status_code == HTTPStatus.CREATED


@shared_task
def setfines_updatedays_autodisburse_rotations_chain():
    """
    Chain the set_fines_and_update_activity_contribution_days, auto_disburse_to_walletts and create_rotations
    """
    logger.info("=chama/tasks.py: setfines_updatedays_autodisburse_rotations_chain()=")
    logger.info(f"Task ran at: {datetime.now()}")
    logger.info(f"Nairobi: {datetime.now(nairobi_tz)}")
    set_fines_task = set_fines_for_missed_contributions.s()
    update_task = update_activities_contribution_days.s()
    auto_disburse_to_wallets = auto_disburse_to_walletts.s()
    create_rotations = create_rotation_contributions.s()
    return chain(
        set_fines_task | update_task | auto_disburse_to_wallets | create_rotations
    )()
