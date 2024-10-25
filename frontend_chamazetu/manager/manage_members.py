import requests, jwt, json, threading, os, calendar
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.contrib import messages
from datetime import datetime
import asyncio, aiohttp
from zoneinfo import ZoneInfo
from http import HTTPStatus
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_chama_data, fetch_data
from chama.chamas import get_chama_id, get_chama_number_of_members, get_chama_name
from member.members import get_user_full_profile, get_user_id
from member.membermanagement import is_empty_dict
from member.date_day_time import extract_date_time
from chama.tasks import (
    update_activities_contribution_days,
    set_contribution_date,
    send_email_invites,
)


from chama.usermanagement import (
    validate_token,
    refresh_token,
    check_token_validity,
)

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")

async def membership_management(request, chama_id):
    return render(request, "manager/membership_management.html", {"chama_id": chama_id})

async def allow_new_members(request, chama_id):
    if request.method == "POST":
        adjustment_fee = request.POST.get("adjustment_fee")
        deadline = request.POST.get("deadline")

        if int(adjustment_fee) and deadline:
            url = f"{os.getenv('api_url')}/managers/allow_new_chama_members/{chama_id}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {request.COOKIES.get('access_token')}"
            }
            data = {
                "late_joining_fee": int(adjustment_fee),
                "deadline": deadline
            }

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == HTTPStatus.CREATED:
                messages.success(request, "New members are now allowed to join this chama.")
            else:
                messages.error(request, f"{response.json().get('detail')}")
        else:
            messages.error(request, "Please fill in all the fields.")

    fallback = reverse("manager:membership_management", args=[chama_id])
    referer = request.META.get("HTTP_REFERER", fallback)
    return HttpResponseRedirect(referer)
