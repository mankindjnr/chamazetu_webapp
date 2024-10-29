import requests, jwt, json, threading, os, calendar
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.middleware.csrf import get_token
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
from chama.tasks import (
    update_activities_contribution_days,
    set_contribution_date,
    send_email_invites,
    create_activity_rotation_contributions,
)

from chama.usermanagement import (
    validate_token,
    refresh_token,
    check_token_validity,
)

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")

# get soft loans manager page
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def get_soft_loans(request, activity_id):
    url = f"{os.getenv('api_url')}/table_banking/soft_loans/manager/{activity_id}"
    response = requests.get(url)

    if response.status_code == HTTPStatus.OK:
        soft_loans = response.json()
        return render(request, "manager/soft_loans.html", {"activity_id": activity_id, "soft_loans": soft_loans})
    else:
        messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)

async def set_update_table_banking_interest_rate(request, activity_id):
    if request.method == "POST":
        interest_rate = request.POST.get("interest_rate")
        if interest_rate:
            interest_rate = float(interest_rate)
            if interest_rate < 5:
                messages.error(request, "Interest rate cannot be negative or less than 5%")
                return redirect("manager:soft_loans", activity_id=activity_id)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            }

            url = f"{os.getenv('api_url')}/table_banking/interest_rate/{activity_id}"
            data = {"interest_rate": interest_rate}

            response = requests.put(url, json=data, headers=headers)
            if response.status_code == HTTPStatus.OK:
                messages.success(request, "Interest rate updated successfully")
            else:
                messages.error(request, f"{response.json().get('detail')}")
        else:
            messages.error(request, "Interest rate cannot be empty")
    

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)

async def update_loan_approval_settings(request, activity_id):
    if request.method == "POST":
        url = f"{os.getenv('api_url')}/table_banking/await_approval/{activity_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }

        response = requests.put(url, headers=headers)
        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Loan approval settings updated successfully")
        else:
            messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def get_loan_settings(request, activity_id):
    url = f"{os.getenv('api_url')}/table_banking/loan_settings/{activity_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    response = requests.get(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        settings = response.json()["loan_settings"]
        return render(request, "manager/loan_settings.html", {"activity_id": activity_id, "settings": settings})
    else:
        messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def loan_eligibility(request, activity_id):
    url = f"{os.getenv('api_url')}/table_banking/loan_eligibility_data/{activity_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        data = response.json()
        eligibility_data = data["eligibility_data"]
        chama_id = data["chama_id"]
        return render(request, "manager/eligibility_settings.html", {"activity_id": activity_id, "chama_id": chama_id, "eligibility_data": eligibility_data})
    else:
        messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)


async def restrict_user(request, activity_id, user_id):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }

        url = f"{os.getenv('api_url')}/table_banking/restrict_user_loan_access/{activity_id}/{user_id}"
        response = requests.put(url, headers=headers)

        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Eligibility settings updated successfully")
        else:
            messages.error(request, f"{response.json().get('detail')}")

        referer = request.META.get("HTTP_REFERER", "member:dashboard")
        return HttpResponseRedirect(referer)

async def allow_user(request, activity_id, user_id):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }

        url = f"{os.getenv('api_url')}/table_banking/allow_loan_access/{activity_id}/{user_id}"
        response = requests.put(url, headers=headers)

        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Eligibility settings updated successfully")
        else:
            messages.error(request, f"{response.json().get('detail')}")

        referer = request.META.get("HTTP_REFERER", "member:dashboard")
        return HttpResponseRedirect(referer)
