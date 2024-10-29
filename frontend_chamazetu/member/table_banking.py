import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse, HttpResponseServerError
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, date, timedelta
from django.contrib import messages
from collections import defaultdict
from http import HTTPStatus
import asyncio, aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from .date_day_time import get_sunday_date, extract_date_time, formatted_date
from .members import (
    get_member_expected_contribution,
    get_user_full_name,
    get_user_id,
    get_member_contribution_so_far,
    get_user_full_profile,
    member_already_in_chama,
)

from chama.chamas import (
    get_chama_id,
)

from chama.usermanagement import (
    validate_token,
    refresh_token,
)

load_dotenv()

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def get_soft_loans_page(request, activity_id):
    url = f"{os.getenv('API_URL')}/table_banking/soft_loans/members/{activity_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == HTTPStatus.OK:
        data = response.json()
        return render(request, "member/soft_loans.html", {"activity_id": activity_id, "data": data})
    else:
        messages.error(request, f"{response.json()['detail']}")
    
    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def request_soft_loan(request, activity_id):
    if request.method == "POST":
        amount = request.POST.get("amount").strip()
        if not amount or amount.isdigit() or int(amount) >= 1000:
            messages.error(request, "Amount must be a number and greater than 999")
            return redirect("member:get_soft_loans_page", activity_id=activity_id)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        eligibility_url = f"{os.getenv('API_URL')}/table_banking/soft_loans/eligibility/{activity_id}"
        eligibility_check = requests.get(eligibility_url, headers=headers)
        
        if eligibility_check.status_code == HTTPStatus.OK:
            url = f"{os.getenv('API_URL')}/table_banking/request_soft_loan/members/{activity_id}"
            data = {
                "amount": int(amount),
                "contribution_day_is_today": eligibility_check.json()["contribution_day_is_today"],
            }
            loan_request = requests.post(url, headers=headers, json=data)
            if loan_request.status_code == HTTPStatus.CREATED:
                messages.success(request, "Soft loan request submitted successfully")
            else:
                messages.error(request, f"{response.json()['detail']}")
        else:
            messages.error(request, f"{eligibility_check.json()['detail']}")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)