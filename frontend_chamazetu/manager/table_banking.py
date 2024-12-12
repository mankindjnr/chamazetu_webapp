import requests, jwt, json, threading, os, calendar
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.middleware.csrf import get_token
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.contrib import messages
from datetime import datetime, date, timedelta
import asyncio, aiohttp
from zoneinfo import ZoneInfo
from http import HTTPStatus
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from chama.decorate.tokens_in_cookies import async_tokens_in_cookies
from chama.decorate.validate_refresh_token import async_validate_and_refresh_token
from chama.chamas import get_chama_id, get_chama_number_of_members, get_chama_name
from member.members import get_user_full_profile, get_user_id

from .manage_activities import last_contribution_date

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")

# get soft loans manager page
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def get_soft_loans(request, activity_id):
    url = f"{os.getenv('api_url')}/table_banking/soft_loans/manager/{activity_id}"
    response = requests.get(url)
    today = datetime.now(nairobi_tz).date()
    one_week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    if response.status_code == HTTPStatus.OK:
        soft_loans = response.json()
        return render(request, "manager/soft_loans.html", {"activity_id": activity_id, "soft_loans": soft_loans, "from_date": one_week_ago, "to_date": today.strftime("%Y-%m-%d")})
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


async def approve_loan(request, activity_id, loan_id):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    url = f"{os.getenv('api_url')}/table_banking/approve_loan/{activity_id}/{loan_id}"
    response = requests.put(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        messages.success(request, "Loan approved successfully")
    else:
        messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)

async def decline_loan(request, activity_id, loan_id):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    url = f"{os.getenv('api_url')}/table_banking/decline_loan/{activity_id}/{loan_id}"
    response = requests.put(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        messages.success(request, "Loan declined successfully")
    else:
        messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def dividend_disbursement(request, activity_id):
    url = f"{os.getenv('api_url')}/table_banking/dividend_disbursement_records/{activity_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == HTTPStatus.OK:
        records = response.json()
        return render(request, "manager/dividend_disbursement_records.html", {"activity_id": activity_id, "role": "manager", "records": records})
    else:
        messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def disburse_dividends(request, activity_id):
    if request.method == "POST":
        today = datetime.now(nairobi_tz).date()
        final_contribution_date = await last_contribution_date(activity_id)
        if final_contribution_date:
            final_contribution_date = datetime.strptime(final_contribution_date, "%Y-%m-%d").date()
            if today < final_contribution_date:
                messages.error(request, "You cannot disburse dividends before the last contribution date")
                referer = request.META.get("HTTP_REFERER", "manager:dashboard")
                return HttpResponseRedirect(referer)
        else:
            messages.error(request, "Please set the last contribution date before disbursement")
            referer = request.META.get("HTTP_REFERER", "manager:dashboard")
            return HttpResponseRedirect(referer)

        request_data = request.POST
        next_date = request_data.get("contribution_date")
        disbursement_type = request_data.get("disbursement_type")

        if not next_date or not disbursement_type or today >= datetime.strptime(next_date, "%Y-%m-%d").date():
            messages.error(request, "Please set the next contribution date and the type of disbursement")
            referer = request.META.get("HTTP_REFERER", "member:dashboard")
            return HttpResponseRedirect(referer)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        url = None
        if disbursement_type == "dividends_and_principal":
            url = f"{os.getenv('api_url')}/table_banking/disburse_dividends_and_principal/{activity_id}"
        elif disbursement_type == "dividends_and_principal_and_fines":
            url = f"{os.getenv('api_url')}/table_banking/disburse_dividends_principal_fines/{activity_id}"

        data = {"next_contribution_date": next_date}

        response = requests.put(url, json=data, headers=headers)

        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Dividends disbursed successfully")
        else:
            messages.error(request, f"{response.json().get('detail')}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)
