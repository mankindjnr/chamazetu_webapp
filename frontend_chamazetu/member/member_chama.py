import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, date
from django.contrib import messages
from collections import defaultdict
from http import HTTPStatus
import asyncio, aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from chama.rawsql import execute_sql
from chama.chamas import (
    get_chama_id,
    get_chama_name,
    get_chama_contribution_day,
    get_previous_contribution_date,
    public_chama_threads,
    get_chama_registration_fee,
    get_next_contribution_date,
)
from chama.thread_urls import fetch_chama_data
from .date_day_time import get_sunday_date, extract_date_time, formatted_date
from .members import (
    get_member_expected_contribution,
    get_user_full_name,
    get_user_id,
    get_member_contribution_so_far,
    get_user_full_profile,
    member_already_in_chama,
)
from manager.managers import get_manager_profile_picture
from .membermanagement import is_empty_dict
from .tasks import (
    update_shares_number_for_member,
    calculate_missed_contributions_fines,
    add_member_to_chama,
    send_email_to_new_chama_member,
    merry_go_round_activity_auto_contributions,
)
from chama.tasks import (
    update_activities_contribution_days,
    set_fines_for_missed_contributions,
    auto_disburse_to_walletts,
    create_rotation_contributions,
    setfines_updatedays_autodisburse_rotations_chain,
    update_accepting_members_chain,
    update_table_banking_loan_records,
)
from manager.tasks import make_late_auto_disbursements

from chama.usermanagement import (
    validate_token,
    refresh_token,
)

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")


# viewing chamas in the public dashboard where users can join
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def view_chama(request, chamaid):
    urls = f"{os.getenv('api_url')}/chamas/info_page/public/{chamaid}"
    resp = requests.get(urls)
    if resp.status_code == HTTPStatus.OK:
        chama = resp.json()
        print("=======logged public access========")
        print(chama)
        return render(
            request,
            "chama/blog_chama.html",
            {
                "role": request.COOKIES.get("current_role"),
                "chama": chama["chama"],
                "rules": chama["rules"],
                "faqs": chama["faqs"],
                "about": chama["about"],
                "manager": chama["manager"],
                "activities": chama["activities"],
            },
        )
    else:
        messages.error(request, "Failed to access chama, try again later")

    return redirect(reverse("chama:chamas"))


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def view_private_chama(request, chamaid):
    urls = f"{os.getenv('api_url')}/chamas/info_page/private/{chamaid}"
    resp = requests.get(urls)
    if resp.status_code == HTTPStatus.OK:
        chama = resp.json()
        return render(
            request,
            "chama/blog_chama.html",
            {
                "role": request.COOKIES.get("current_role"),
                "chama": chama["chama"],
                "rules": chama["rules"],
                "faqs": chama["faqs"],
                "about": chama["about"],
                "manager": chama["manager"],
                "activities": chama["activities"],
            },
        )
    else:
        messages.error(
            request, "Failed to access private chama, please try again later"
        )

    return redirect(reverse("member:dashboard"))

# this will take chama_id, get its name and redirect to the access_chama view
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def get_chama_view(request, chama_id):
    chama_name = get_chama_name(chama_id)
    return redirect(reverse("member:access_chama", args=[chama_name, chama_id]))

# viewing a chamas in the member dashboard where they can interact with specifc chama
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def access_chama(request, chamaname, chama_id):
    current_user = request.COOKIES.get("current_user")
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    chama = requests.get(
        f"{os.getenv('api_url')}/members/chama_dashboard/{chama_id}", headers=headers
    )

    if chama.status_code == HTTPStatus.OK:
        # set_fines_for_missed_contributions.delay()
        # update_activities_contribution_days.delay()
        # auto_disburse_to_walletts.delay()
        # create_rotation_contributions.delay()
        setfines_updatedays_autodisburse_rotations_chain.delay()
        # update_table_banking_loan_records.delay()
        # merry_go_round_activity_auto_contributions.delay()
        # make_late_auto_disbursements.delay()
        # update_accepting_members_chain.delay()
        chama_data = chama.json()
        return render(
            request,
            "member/chamadashboard.html",
            {
                "current_user": current_user,
                "chama_id": chama_data["chama_id"],
                "chama_name": chama_data["chama_name"],
                "wallet_balance": chama_data["wallet_balance"],
                "account_balance": chama_data["account_balance"],
                "available_balance": chama_data["available_balance"],
                "total_fines": chama_data["total_fines"],
                "chama_activities": chama_data["chama_activities"],
            },
        )
    else:
        messages.error(request, "Failed to access chama, try again later")
        return HttpResponseRedirect(reverse("member:dashboard"))
    return HttpResponseRedirect(reverse("member:dashboard"))


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def join_chama(request):
    if request.method == "POST":
        chama_name = request.POST.get("chamaname")
        reg_fee = request.POST.get("registration_fee")
        phone_number = request.POST.get("phone_number")
        chama_id = get_chama_id(chama_name)
        registration_fee = get_chama_registration_fee(chama_id)
        user_id = get_user_id(request.COOKIES.get("current_user"))

        if not phone_number or not phone_number.isdigit() or len(phone_number) != 10:
            messages.error(request, "Invalid phone number")
            return HttpResponseRedirect(reverse("chama:chamas"))

        if member_already_in_chama(chama_id, user_id):
            messages.error(request, "You are already a member of this chama")
            return HttpResponseRedirect(reverse("chama:chamas"))

        # confirm if the needed details are there, that is the chamaname, num_of_shares and the registration amount, also, retrieve the registration fee for that chama
        if chama_name and reg_fee and request.COOKIES.get("access_token"):
            timestamp = datetime.now(nairobi_tz).strftime("%Y%m%d%H%M%S")

            if registration_fee == 0:
                url = f"{os.getenv('api_url')}/chamas/add_member"
                data = {
                    "chama_id": chama_id,
                    "user_id": user_id,
                }

                response = requests.post(url, json=data)
                if response.status_code == HTTPStatus.CREATED:
                    # send_email_to_new_member
                    messages.success(request, "You have successfully joined the chama")
                    return HttpResponseRedirect(reverse("member:dashboard"))
                else:
                    messages.error(
                        request,
                        f"{response.json().get('detail')}, please try again later",
                    )
            else:
                # record unprocessed request
                unprocessed_request = requests.post(
                    f"{os.getenv('api_url')}/transactions/unprocessed_deposit",
                    json={
                        "amount": registration_fee,
                        "transaction_type": "unprocessed registration fee",
                        "transaction_origin": f"254{phone_number[1:]}",
                        "transaction_destination": f"{chama_id}Registration",
                        "user_id": user_id,
                    },
                )

                if unprocessed_request.status_code == HTTPStatus.CREATED:
                    reg_resp = requests.post(
                        f"{os.getenv('api_url')}/request/push",
                        json={
                            "phone_number": f"254{phone_number[1:]}",
                            "amount": registration_fee,
                            "transaction_destination": (chama_name.replace(" ", ""))[
                                :12
                            ],
                            "transaction_code": unprocessed_request.json()[
                                "transaction_code"
                            ],
                            "description": "Registration",
                        },
                    )
                    if reg_resp.status_code == HTTPStatus.CREATED:
                        # one bg task to add use to the member_chama table after we verify the payment status
                        send_email_to_new_chama_member.delay(user_id)
                        messages.success(
                            request,
                            "Your chama registration request has been sent, please check your email for a confirmation message",
                        )
                        return HttpResponseRedirect(reverse("member:dashboard"))
                    else:
                        messages.error(
                            request, "Failed to join chama, please try again later"
                        )
                else:
                    messages.error(
                        request, f"{unprocessed_request.json().get('detail')}"
                    )

        else:
            messages.error(request, "Please fill in all the fields")

    return HttpResponseRedirect(reverse("chama:chamas"))


@tokens_in_cookies()
@validate_and_refresh_token()
def view_chama_members(request, chama_name, chama_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    role = request.COOKIES.get("current_role")

    chama_members = requests.get(
        f"{os.getenv('api_url')}/chamas/members/{chama_id}",
        headers=headers,
    )
    print("=======chama members=========")
    print(chama_members.json())
    return render(
        request,
        "member/list_members.html",
        {
            "role": role,
            "item_id": chama_id,
            "members": chama_members.json(),
            "title": chama_name,
        },
    )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def get_about_chama(request, chama_name, chama_id):
    user_id = get_user_id(request.COOKIES.get("current_user"))
    role = request.COOKIES.get("current_role")
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    chama_data = requests.get(
        f"{os.getenv('api_url')}/chamas/about_chama/{chama_id}",
        headers=headers,
    )

    if chama_data.status_code == HTTPStatus.OK:
        # print(chama_data.json())
        chama = chama_data.json().get("chama")
        rules = chama_data.json().get("rules")
        about = chama_data.json().get("about")
        faqs = chama_data.json().get("faqs")

        return render(
            request,
            "chama/about_chama.html",
            {
                "profile_picture": chama_data.json().get("profile_picture"),
                "chama": chama,
                "rules": rules,
                "about": about,
                "faqs": faqs,
                "user_id": user_id,
                "role": role,
                "is_manager": chama_data.json().get("is_manager"),
                "chama_id": chama_id,
                "chama_data": chama_data.json(),
            },
        )
    else:
        return redirect(reverse(f"{role}:dashboard"))


def chama_details_organised(chama_details):
    chama_details["number_of_members_allowed"] = (
        "No Limit"
        if chama_details["num_of_members_allowed"] == "infinite"
        else chama_details["num_of_members_allowed"]
    )
    chama_details["description"] = chama_details["description"]
    chama_details["chama_type"] = chama_details["chama_type"].capitalize()
    chama_details["account_name"] = (
        (chama_details["chama_name"]).replace("_", "").lower()
    )
    chama_details["registration_fee"] = (
        f"Ksh: {(chama_details['registration_fee']):,.2f}"
    )
    chama_details["chama_created_on"] = extract_date_time(
        chama_details["date_created"]
    )["date"]

    # chama_details["chama_start_date"] = extract_date_time(chama_details["last_joining_date"])[
    #     "date"
    # ]
    chama_details["chama_is_active"] = (
        "Active" if chama_details["is_active"] else "Inactive"
    )
    chama_details["manager_number"] = chama_details["manager_id"]
    chama_details["manager_profile_picture"] = get_manager_profile_picture(
        chama_details["manager_id"]
    )
    chama_details["accepting_new_members"] = (
        "Accepting Members"
        if chama_details["accepting_members"]
        else "Not Accepting Members"
    )
    del chama_details["num_of_members_allowed"]
    del chama_details["date_created"]
    del chama_details["last_joining_date"]
    del chama_details["updated_at"]
    del chama_details["restart"]
    del chama_details["is_deleted"]
    del chama_details["manager_id"]
    del chama_details["is_active"]
    del chama_details["accepting_members"]
    del chama_details["first_contribution_date"]
    return chama_details


def auto_contribute_settings(request, chama_id, member_id, status):
    if status == "activate":
        expected_contribution = get_member_expected_contribution(member_id, chama_id)
        next_contribution_date = get_next_contribution_date(chama_id)
        data = {
            "member_id": member_id,
            "chama_id": chama_id,
            "expected_amount": expected_contribution,
            "next_contribution_date": next_contribution_date,
            "status": status,
        }
        url = f"{os.getenv('api_url')}/members/auto_contribute"
        response = requests.post(url, json=data)
        if response.status_code == HTTPStatus.CREATED:
            messages.success(request, "Successfully activated auto contribute")
            return redirect(
                reverse("member:get_about_chama", args=[request.POST.get("chama_name")])
            )
        else:
            messages.error(request, "Failed to activate auto contributions")
            return redirect(
                reverse("member:get_about_chama", args=[request.POST.get("chama_name")])
            )
    else:
        url = f"{os.getenv('api_url')}/members/auto_contribute/{chama_id}/{member_id}"
        response = requests.delete(url)
        if response.status_code == HTTPStatus.OK:
            messages.success(
                request, "You have successfully deactivated auto contribute"
            )
            return redirect(
                reverse("member:get_about_chama", args=[request.POST.get("chama_name")])
            )
        else:
            messages.error(request, "Failed to deactivate auto contributions")
            return redirect(
                reverse("member:get_about_chama", args=[request.POST.get("chama_name")])
            )

    return redirect(reverse("member:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def chama_activities(request, chama_name, chama_id):
    resp = requests.get(
        f"{os.getenv('api_url')}/activities/chama/{chama_id}",
        headers={
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        },
    )

    if resp.status_code == HTTPStatus.OK:
        return render(
            request,
            "member/activities_list.html",
            {"chama_id": chama_id, "activities": resp.json(), "chama_name": chama_name},
        )
    else:
        messages.error(request, "Failed to fetch chama activities")
        return HttpResponseRedirect(
            reverse("member:access_chama", args=[chama_name, chama_id])
        )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def investment_marketplace(request, chama_id):
    url = f"{os.getenv('api_url')}/chamas/investment_marketplace/{chama_id}"

    response = requests.get(url)
    if response.status_code == HTTPStatus.OK:
        marketplace_investments = response.json()["investment_marketplace"]
        return render(
            request,
            "manager/investment_marketplace.html",
            {
                "role": "member",
                "chama_id": chama_id,
                "marketplace_investments": marketplace_investments,
            },
        )
    else:
        messages.error(request, "Failed to fetch marketplace data")

    referer = request.META.get("HTTP_REFERER", reverse("member:dashboard"))
    return HttpResponseRedirect(referer)