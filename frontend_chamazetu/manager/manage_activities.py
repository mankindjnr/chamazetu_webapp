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

# return to the previous page
def go_back(request):
    referer = request.META.get("HTTP_REFERER", reverse("manager:dashboard"))
    return HttpResponseRedirect(referer)


# accessing rotating contributions page
async def rotating_order(request, activity_id):
    url = f"{os.getenv('API_URL')}/activities/rotation_order/{activity_id}"
    headers = {
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        "Content-Type": "application/json",
    }
    rotation_resp = requests.get(url, headers=headers)
    if rotation_resp.status_code == HTTPStatus.OK:
        rotation_data = rotation_resp.json()
        print("========rotation_data========")
        # print(rotation_data)
        return render(
            request,
            "manager/rotation_order.html",
            {
                "pooled": rotation_data["pooled_so_far"],
                "activity_id": rotation_data["activity_id"],
                "activity_name": rotation_data["activity_name"],
                "upcoming_recipient": rotation_data["upcoming_recipient"],
                "rotation_order": rotation_data["rotation_order"],
                "rotation_date": rotation_data["rotation_date"],
                "new_rotation_needed": rotation_data["new_rotation_needed"],
            },
        )

    return HttpResponseRedirect(reverse("manager:dashboard"))


# creating a randomized rotation order
@require_POST
async def create_random_rotation_order(request, activity_id):
    # extract the csrf token from the request
    csrf_token = get_token(request)

    # data to be sent to the API - wont be used in this case
    data = {
        "activity_id": activity_id,
        "csrfmiddlewaretoken": csrf_token,  # for csrf protection
    }

    # call the API to create a random rotation order
    try:
        url = f"{os.getenv('API_URL')}/managers/random_rotation_order/{activity_id}"
        headers = {
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            "Content-Type": "application/json",
        }
        rotation_resp = requests.post(url, headers=headers)
        if rotation_resp.status_code == HTTPStatus.CREATED:
            # create the rotation contributions upon successful creation of the rotation order
            create_activity_rotation_contributions.delay(activity_id)
            messages.success(request, "Rotation order created successfully")
            return JsonResponse(
                {"success": True, "message": "Rotation order created successfully"}
            )
        else:
            return JsonResponse(
                {"success": False, "message": "Failed to create rotation order"}
            )
    except requests.exceptions.RequestException as e:
        print(e)
        return JsonResponse(
            {"success": False, "message": "Failed to create rotation order"}
        )

    return HttpResponseRedirect(reverse("manager:rotating_order", args=[activity_id]))


async def disburse_funds(request, activity_id):
    if request.method != "POST":
        return HttpResponseRedirect(
            reverse("manager:rotating_order", args=[activity_id])
        )

    url = f"{os.getenv('API_URL')}/managers/disburse_funds/{activity_id}"
    headers = {
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        "Content-Type": "application/json",
    }
    disburse_resp = requests.post(url, headers=headers)
    if disburse_resp.status_code == HTTPStatus.CREATED:
        messages.success(request, "Funds disbursed successfully")
    else:
        messages.error(request, "Failed to disburse funds, please try again")

    return HttpResponseRedirect(reverse("manager:rotating_order", args=[activity_id]))


async def fines_tracker(request, activity_name, activity_id, from_date, to_date):
    url = f"{os.getenv('api_url')}/activities/fines/{activity_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    data = {"from_date": from_date, "to_date": to_date}
    response = requests.get(url, json=data, headers=headers)

    if response.status_code == HTTPStatus.OK:
        fines_data = response.json()
        return render(
            request,
            "member/fines_tracker.html",
            {
                "role": "manager",
                "activity_name": activity_name,
                "activity_id": activity_id,
                "fines": fines_data,
                "dates": data,
            },
        )
    else:
        messages.error(request, f"{response.json().get('detail')}")
    
    referer = request.META.get("HTTP_REFERER", "manager:dashboard")
    return HttpResponseRedirect(referer)
        

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def order_management(request, activity_id):
    return render(request, "manager/order_management.html", {"activity_id": activity_id})


async def merry_go_round_share_increase(request, activity_id):
    if request.method == "POST":
        url = f"{os.getenv('API_URL')}/managers/allow_members_to_increase_shares/{activity_id}"
        headers = {
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            "Content-Type": "application/json",
        }

        # get the data from the form
        max_no_shares = request.POST.get("max_addon")
        deadline_date = request.POST.get("deadline")
        late_fee = request.POST.get("late_fee")
        notify = request.POST.get("notify")
        dont_notify = request.POST.get("dont_notify")

        if max_no_shares == "" or deadline_date == "" or late_fee == "" or (notify == "" and dont_notify == ""):
            messages.error(request, "Please fill in all fields")
            return HttpResponseRedirect(reverse("manager:order_management", args=[activity_id]))

        # TODO: if notify members - bg task to send emails to all members
        notify_members = None
        if notify == "on":
            notify_members = True
        elif dont_notify == "on":
            notify_members = False

        data = {
            "max_no_shares": max_no_shares,
            "deadline_date": deadline_date,
            "adjustment_fee": late_fee,
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == HTTPStatus.CREATED:
            messages.success(request, "Members can now increase their shares")
        else:
            messages.error(request, f"{response.json()['detail']}")

    return HttpResponseRedirect(reverse("manager:order_management", args=[activity_id]))

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def allow_new_activity_members(request, activity_id):
    if request.method == "POST":
        url = f"{os.getenv('API_URL')}/managers/allow_new_members_to_join/{activity_id}"
        headers = {
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            "Content-Type": "application/json",
        }

        # get the data from the form(deadline, adjustment fee, max_shares)
        if not request.POST.get("deadline") or not request.POST.get("late_fee") or not request.POST.get("max_shares"):
            messages.error(request, "Please fill in all fields")
            fallback = reverse("manager:order_management", args=[activity_id])
            referer = request.META.get("HTTP_REFERER", fallback)
            return HttpResponseRedirect(referer)

        deadline = request.POST.get("deadline")
        adjustment_fee = request.POST.get("late_fee")
        max_shares = request.POST.get("max_shares")

        data = {
            "deadline_date": deadline,
            "adjustment_fee": adjustment_fee,
            "max_no_shares": int(max_shares)
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == HTTPStatus.CREATED:
            messages.success(request, "New members can now join this activity")
        else:
            messages.error(request, f"{response.json()['detail']}")

    return redirect(reverse("manager:order_management", args=[activity_id]))

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def investment_marketplace(request, chama_id):
    url = f"{os.getenv('API_URL')}/chamas/investment_marketplace/{chama_id}"

    response = requests.get(url)
    if response.status_code == HTTPStatus.OK:
        marketplace_investments = response.json()["investment_marketplace"]
        return render(
            request,
            "manager/investment_marketplace.html",
            {
                "role": "manager",
                "chama_id": chama_id,
                "marketplace_investments": marketplace_investments,
            },
        )
    else:
        messages.error(request, "Failed to fetch marketplace data")

    referer = request.META.get("HTTP_REFERER", reverse("manager:dashboard"))
    return HttpResponseRedirect(referer)

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def set_last_contribution_date(request, activity_id):
    if request.method == "POST":
        url = f"{os.getenv('API_URL')}/activities/last_contribution_date/{activity_id}"
        headers = {
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            "Content-Type": "application/json",
        }

        # get the data from the form
        last_contribution_date = request.POST.get("final_date")
        if not last_contribution_date:
            messages.error(request, "Please select a date")
            return go_back(request)

        data = {
            "last_contribution_date": last_contribution_date,
        }

        response = requests.put(url, headers=headers, json=data)
        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Final contribution date set successfully")
        else:
            messages.error(request, f"{response.json()['detail']}")

    return go_back(request)

async def last_contribution_date(activity_id):
    url = f"{os.getenv('API_URL')}/activities/last_contribution_date/{activity_id}"
    response = requests.get(url)
    if response.status_code == HTTPStatus.OK:
        return response.json()["last_contribution_date"]
    return None


async def transfer_fines(request, activity_id):
    pass