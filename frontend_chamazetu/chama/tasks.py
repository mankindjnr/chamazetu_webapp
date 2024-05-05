from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.core.mail import send_mail
import requests, os
from dotenv import load_dotenv

from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib import messages
from frontend_chamazetu import settings

load_dotenv()


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


# update the contribution days for the chamas
@shared_task
def update_contribution_days():
    """
    Update the next contribution day for chamas
    """
    response = requests.put(f"{os.getenv('api_url')}/chamas/update_contribution_days")

    return None


# calculate daily interests for the chamas
@shared_task
def calaculate_daily_mmf_interests():
    """
    Calculate daily interests for the chamas
    """
    response = requests.put(
        f"{os.getenv('api_url')}/investments/chamas/calculate_daily_mmf_interests"
    )

    return None


@shared_task
def reset_and_move_weekly_mmf_interests():
    """
    Reset and add weekly mmf interests to the principal
    """
    response = requests.put(
        f"{os.getenv('api_url')}/investments/chamas/reset_and_move_weekly_mmf_interest_to_principal"
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

    return None
