from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.core.mail import send_mail
from decouple import config
import requests

from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib import messages
from frontend_chamazetu import settings


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
