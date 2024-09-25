import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
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


# work on detecting if the user is already in the activity
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def join_activity(request, chama_name, activity_id):
    if request.method == "POST":
        print("=====join activity=====")
        print("----", activity_id)

        chama_id = get_chama_id(chama_name)
        if await member_in_activity(request, activity_id):
            messages.error(request, "You are already in the activity")
            return HttpResponseRedirect(
                reverse(
                    "member:access_chama",
                    args=[chama_name, chama_id],
                )
            )
        shares = request.POST.get("shares")
        print("=====share====")
        print(shares)
        headers = {
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            "Content-Type": "application/json",
        }

        data = {
            "shares": shares,
        }
        resp = requests.post(
            f"{os.getenv('api_url')}/activities/join/{activity_id}",
            headers=headers,
            json=data,
        )

        if resp.status_code == HTTPStatus.CREATED:
            messages.success(request, "You have successfully joined the activity")
            return HttpResponseRedirect(
                reverse(
                    "member:access_chama",
                    args=[chama_name, chama_id],
                )
            )

    messages.error(request, "Failed to join the activity, please try again")
    return HttpResponseRedirect(
        reverse(
            "member:chama_activities",
            args=[chama_name, chama_id],
        )
    )


# work on detecting if the user is already in the activity
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def member_in_activity(request, activity_id):
    headers = {
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        "Content-Type": "application/json",
    }

    resp = requests.get(
        f"{os.getenv('api_url')}/activities/{activity_id}/member",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        data = resp.json()
        if data["member_in_activity"]:
            return True

    return False


# @async_tokens_in_cookies()
# @async_validate_and_refresh_token()
# async def access_activity(request, chama_name, chama_id, activity_type, activity_id):
#     headers = {
#         "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
#         "Content-Type": "application/json",
#     }
#     if activity_type == "merry-go-round":
#         return await merry_go_round(
#             request, chama_name, chama_id, activity_type, activity_id, headers
#         )
#     elif activity_type in ["saving", "investment", "welfare"]:
#         return await generic_activity(
#             request, chama_name, chama_id, activity_type, activity_id, headers
#         )

#     return HttpResponseRedirect(
#         reverse("member:access_chama", args=[chama_name, chama_id])
#     )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def access_activity(request, chama_name, chama_id, activity_type, activity_id):
    headers = {
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        "Content-Type": "application/json",
    }

    activity_data = await get_activity_data(request, activity_id, headers)
    recent_transactions = await get_recent_activity_transactions(request, activity_id)

    weekly_contributions = None
    weekly_headers = None
    if activity_data["activity_frequency"] == "weekly":
        weekly_contributions, weekly_headers = (
            await organise_weekly_group_contributions(
                activity_data["weekly_contributions"],
                activity_data["activity_amount"],
                activity_data["activity_id"],
                activity_data["activity_frequency"],
                activity_data["previous_contribution_date"],
                activity_data["next_contribution_date"],
            )
        )
    else:
        weekly_contributions = await organise_weekly_contributions(
            activity_data["weekly_contributions"],
            activity_data["activity_amount"],
            activity_data["activity_id"],
            activity_data["activity_frequency"],
        )
    if activity_data:
        return render(
            request,
            "member/activity.html",
            {
                "chama_name": chama_name,
                "chama_id": chama_id,
                "activity_id": activity_data["activity_id"],
                "activity_name": activity_data["activity_name"],
                "activity_type": activity_data["activity_type"],
                "amount": activity_data["activity_amount"],
                "account_balance": activity_data["activity_balance"],
                "my_fines": activity_data["unpaid_fines"],
                "contribution_date": activity_data["next_contribution_date"],
                "recent_transactions": recent_transactions,
                "today_contributions": activity_data["today_contributions"],
                "weekly_headers": weekly_headers,
                "weekly_contributions": weekly_contributions,
                "wallet_balance": activity_data["wallet_balance"],
            },
        )
    return HttpResponseRedirect(
        reverse("member:access_chama", args=[chama_name, chama_id])
    )


async def generic_activity(
    request, chama_name, chama_id, activity_type, activity_id, headers
):
    if activity_type in ["saving", "investment", "welfare"]:
        activity_data = await generic_activity_data(request, activity_id, headers)
        recent_transactions = await get_recent_activity_transactions(
            request, activity_id
        )

        weekly_contributions = None
        weekly_headers = None
        if activity_data["activity_frequency"] == "weekly":
            weekly_contributions, weekly_headers = (
                await organise_weekly_group_contributions(
                    activity_data["weekly_contributions"],
                    activity_data["activity_amount"],
                    activity_data["activity_id"],
                    activity_data["activity_frequency"],
                    activity_data["previous_contribution_date"],
                    activity_data["next_contribution_date"],
                )
            )
        else:
            weekly_contributions = await organise_weekly_contributions(
                activity_data["weekly_contributions"],
                activity_data["activity_amount"],
                activity_data["activity_id"],
                activity_data["activity_frequency"],
            )
        if activity_data:
            return render(
                request,
                "member/generic_activity.html",
                {
                    "chama_name": chama_name,
                    "chama_id": chama_id,
                    "activity_id": activity_data["activity_id"],
                    "activity_name": activity_data["activity_name"],
                    "activity_type": activity_data["activity_type"],
                    "amount": activity_data["activity_amount"],
                    "account_balance": activity_data["activity_balance"],
                    "my_fines": activity_data["unpaid_fines"],
                    "contribution_date": activity_data["next_contribution_date"],
                    "recent_transactions": recent_transactions,
                    "today_contributions": activity_data["today_contributions"],
                    "weekly_contributions": weekly_contributions,
                    "weekly_headers": weekly_headers,
                    "wallet_balance": activity_data["wallet_balance"],
                },
            )
    return HttpResponseRedirect(
        reverse("member:access_chama", args=[chama_name, chama_id])
    )


# weekly_contributions = [{'user_id': 1, 'amount': 10, 'date': '2024-09-03T17:03:42', 'first_name': 'nurtu', 'last_name': 'posta', 'shares': 1}]
async def organise_weekly_contributions(
    weekly_contributions_raw, activity_amount, activity_id, frequency
):
    weekly_data = defaultdict(
        lambda: {
            "user_name": "",
            "user_id": 0,
            "shares": 0,
            "Sunday": 0,
            "Monday": 0,
            "Tuesday": 0,
            "Wednesday": 0,
            "Thursday": 0,
            "Friday": 0,
            "Saturday": 0,
        }
    )

    # print("=====weekly_contributions data=====")
    # print(frequency, "\n")
    # print(weekly_contributions_raw)

    # loop through the weekly contributions
    for contribution in weekly_contributions_raw:
        user_name = f"{contribution['first_name']} {contribution['last_name']}"
        user_id = contribution["user_id"]
        shares = contribution["shares"]
        # convert the date to a datetime object to find the day of the week
        date = datetime.strptime(contribution["date"], "%Y-%m-%d")
        day_of_week = date.strftime("%A")  # full name of the day of the week

        # add the amount to the corresponding day for that user
        weekly_data[(user_id, shares)]["user_name"] = user_name
        weekly_data[(user_id, shares)]["user_id"] = user_id
        weekly_data[(user_id, shares)]["shares"] = shares
        weekly_data[(user_id, shares)][day_of_week] += contribution["amount"]

    # format output as a list of dictionaries
    weekly_contributions_refined = [value for value in weekly_data.values()]

    # loop through the weekly contributions and add the expected and contributed
    for contribution in weekly_contributions_refined:
        user_id = contribution["user_id"]
        shares = contribution["shares"]
        expected = activity_amount * shares
        contributed = get_member_contribution_so_far(user_id, activity_id)
        contribution["expected"] = expected
        contribution["contributed"] = contributed

    print("=====refined output=====")
    print(weekly_contributions_refined)

    return weekly_contributions_refined


# we are goin to redo the above route with a focus on a weekly group contribution, this type of group we will display
#  differently in that, instead of from sunday to saturday, we will display from the last contribution day to the next
# this could be from tuesday to monday, or from friday to thursday
# everythign else will be the same, the user name, the amount contributed, the amount expected, the shares, the user id
async def organise_weekly_group_contributions(
    weekly_contributions_raw,
    activity_amount,
    activity_id,
    frequency,
    previous_date,
    next_date,
):

    # get the days of the week represented by the dates from > previous_date to <= next_date
    days_of_week = []
    previous_date = datetime.strptime(previous_date, "%d-%B-%Y")
    parsed_previous_date = previous_date.strftime("%Y-%m-%d")
    next_date = datetime.strptime(next_date, "%d-%B-%Y")
    parsed_next_date = next_date.strftime("%Y-%m-%d")

    start_date = (datetime.strptime(parsed_previous_date, "%Y-%m-%d")) + timedelta(
        days=1
    )
    end_date = datetime.strptime(parsed_next_date, "%Y-%m-%d")
    while start_date <= end_date:
        days_of_week.append(
            {start_date.strftime("%A"): start_date.strftime("%Y-%m-%d")}
        )
        start_date += timedelta(days=1)

    # print("=====days of the week=====")
    # print(days_of_week)

    # initialize result dictionary for each user
    result = defaultdict(
        lambda: {
            "user_name": "",
            "user_id": 0,
            "shares": 0,
            **{day: 0 for day in [list(day.keys())[0] for day in days_of_week]},
        }
    )

    # convert days_of_week list to a dictionary with day names as keys and dates as values
    date_mapping = {
        day: datetime.strptime(date, "%Y-%m-%d").date()
        for day_dict in days_of_week
        for day, date in day_dict.items()
    }

    # process each contribution and match with the respective day in the date mapping
    for contribution in weekly_contributions_raw:
        user_name = f"{contribution['first_name']} {contribution['last_name']}"
        user_id = contribution["user_id"]
        shares = contribution["shares"]
        contribution_date = datetime.strptime(contribution["date"], "%Y-%m-%d").date()

        # find the corresponding day f te week for the contributiion date
        for day, date in date_mapping.items():
            if contribution_date == date:
                result[(user_id, shares)]["user_name"] = user_name
                result[(user_id, shares)]["user_id"] = user_id
                result[(user_id, shares)]["shares"] = shares
                result[(user_id, shares)][day] += contribution["amount"]

    # return the result as alist of dictionaries
    final_result = [value for value in result.values()]

    # print("=====final result=====")
    # print(final_result)

    # loop through the weekly contributions and add the expected and contributed
    for contribution in final_result:
        user_id = contribution["user_id"]
        shares = contribution["shares"]
        expected = activity_amount * shares
        contributed = get_member_contribution_so_far(user_id, activity_id)
        contribution["expected"] = expected
        contribution["contributed"] = contributed

    headers = list(final_result[0].keys()) if final_result else []
    if headers:
        headers.remove("user_id")
        headers.remove("shares")
    else:
        headers = [list(day.keys())[0] for day in days_of_week]

    # Ensure 'expected' and 'contributed' come after 'user_name'
    weekly_headers = ["user_name", "expected", "contributed"] + [
        header
        for header in headers
        if header not in ["user_name", "expected", "contributed"]
    ]

    return (final_result, weekly_headers)


async def merry_go_round_activity(request, activity_id, headers):
    resp = requests.get(
        f"{os.getenv('api_url')}/activities/merry-go-round/{activity_id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        data = resp.json()
        print("=====merry-go-round data=====")
        print(data)
        return data
    else:
        return None


async def get_activity_data(request, activity_id, headers):
    resp = requests.get(
        f"{os.getenv('api_url')}/activities/activity_data/{activity_id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        data = resp.json()
        print("====generic data=====")
        print(data)
        return data
    else:
        return None


# this will retrieve both the recent activity member transactions and also those done by the manager in that activity account
async def get_recent_activity_transactions(request, activity_id):
    resp = requests.get(
        f"{os.getenv('api_url')}/activities/recent_transactions/{activity_id}",
    )

    if resp.status_code == HTTPStatus.OK:
        data = resp.json()
        # print("=====recent activity transactions=====")
        # print(data)
        return data

    return None


def get_activity_info(activity_name):
    resp = requests.get(
        f"{os.getenv('api_url')}/activities/id/{activity_name}",
    )

    if resp.status_code == HTTPStatus.OK:
        data = resp.json()
        print("=====activity_id=====")
        print(data["activity_id"])
        return (data["activity_id"], data["activity_type"])

    return None


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def view_activity_members(request, activity_name, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    activity_members = requests.get(
        f"{os.getenv('api_url')}/activities/members/{activity_id}",
        headers=headers,
    )
    print("=======activity members=========")
    print(activity_members.json())
    return render(
        request,
        "member/list_members.html",
        {
            "type": "activity",
            "item_id": activity_id,
            "members": activity_members.json(),
            "title": activity_name,
        },
    )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def get_about_activity(request, activity_name, activity_id):
    user_id = get_user_id(request.COOKIES.get("current_user"))
    role = request.COOKIES.get("current_role")
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    activity_data = requests.get(
        f"{os.getenv('api_url')}/activities/about/{activity_id}",
        headers=headers,
    )
    auto_contribute_status = requests.get(
        f"{os.getenv('api_url')}/members/auto_contribute_status/{activity_id}/{user_id}",
    )
    if auto_contribute_status.status_code == HTTPStatus.OK:
        auto_contribute_status = auto_contribute_status.json()["status"]

    print("=============activity about================")
    if activity_data.status_code == HTTPStatus.OK:
        print(auto_contribute_status)
        return render(
            request,
            "chama/about_activity.html",
            {
                "role": role,
                "auto_contribute_status": auto_contribute_status,
                "activity": activity_data.json(),
            },
        )
    else:
        return redirect(reverse(f"{role}:dashboard"))


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def activate_auto_contributions(request, activity_name, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.post(
        f"{os.getenv('api_url')}/members/auto_contribute/{activity_id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.CREATED:
        messages.success(request, "Auto contributions status updated")
    else:
        messages.error(request, "Failed to activate auto contributions")

    return HttpResponseRedirect(
        reverse("member:get_about_activity", args=[activity_name, activity_id])
    )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def deactivate_auto_contributions(request, activity_name, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.delete(
        f"{os.getenv('api_url')}/members/auto_contribute/{activity_id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        messages.success(request, "Auto contributions status updated")
    else:
        messages.error(request, "Failed to deactivate auto contributions")

    return HttpResponseRedirect(
        reverse("member:get_about_activity", args=[activity_name, activity_id])
    )
