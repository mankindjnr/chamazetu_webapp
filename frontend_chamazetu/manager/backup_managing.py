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

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_chama_data, fetch_data
from chama.chamas import get_chama_id, get_chama_number_of_members
from member.member_chama import (
    access_chama_async,
    recent_transactions,
    chama_details_organised,
    organise_mmf_withdrawal_activity,
)
from member.members import get_user_full_profile, get_user_id
from member.membermanagement import is_empty_dict
from member.date_day_time import extract_date_time
from chama.tasks import update_contribution_days, set_contribution_date


from chama.usermanagement import (
    validate_token,
    refresh_token,
)

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")


@tokens_in_cookies()
@validate_and_refresh_token()
def dashboard(request):
    current_user = request.COOKIES.get("current_user")
    manager_id = get_user_id(current_user)
    current_role = request.COOKIES.get("current_role")
    print("===========manager dashboard================")
    print(current_user, ":", current_role, ":", manager_id)

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    urls = (
        (f"{os.getenv('api_url')}/managers/chamas", {}),
        (f"{os.getenv('api_url')}/managers/updates_and_features", None),
        (f"{os.getenv('api_url')}/managers/profile_picture", {}),
    )
    dashboard_results = manager_dashboard_threads(urls, headers)

    return render(
        request,
        "manager/dashboard.html",
        {
            "current_user": current_user,
            "current_role": current_role,
            "manager_id": manager_id,
            "profile_picture": dashboard_results["profile_picture"],
            "chamas": dashboard_results["chamas"],
            "updates_and_features": dashboard_results["updates_and_features"],
        },
    )


def manager_dashboard_threads(urls, headers):
    results = {}
    threads = []

    for url, payload in urls:
        if payload:
            thread = threading.Thread(
                target=fetch_data, args=(url, results, payload, headers)
            )
        elif is_empty_dict(payload):
            thread = threading.Thread(
                target=fetch_data, args=(url, results, {}, headers)
            )
        else:
            thread = threading.Thread(target=fetch_data, args=(url, results))

        threads.append(thread)
        thread.start()

    # wait for all threads to finish
    for thread in threads:
        thread.join()

    chamas = None
    updates_and_features = None
    profile_picture = None

    if results[urls[0][0]]["status"] == 200:
        manager_chamas = results[urls[0][0]]["data"]
        list_of_chamas = []
        for item in manager_chamas:
            item["number_of_members"] = get_chama_number_of_members(
                get_chama_id(item["chama_name"])
            )
            list_of_chamas.append(item)

        chamas = list_of_chamas
    if results[urls[1][0]]["status"] == 200:
        updates_and_features = results[urls[1][0]]["data"]
    if results[urls[2][0]]["status"] == 200:
        profile_picture = results[urls[2][0]]["data"]
    print("===================================")
    print(chamas)
    return {
        "chamas": chamas,
        "updates_and_features": updates_and_features,
        "profile_picture": profile_picture,
    }


@tokens_in_cookies()
@validate_and_refresh_token()
def get_about_chama(request, chama_name):
    chama_id = get_chama_id(chama_name)
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    chama_data = requests.get(
        f"{os.getenv('api_url')}/chamas/about_chama/{chama_id}",
        headers=headers,
    )
    print("===================================")
    if chama_data.status_code == 200:
        chama = chama_details_organised(chama_data.json().get("chama"))
        rules = chama_data.json().get("rules")
        about = chama_data.json().get("about")
        faqs = chama_data.json().get("faqs")

        return render(
            request,
            "chama/about_chama.html",
            {
                "role": "manager",
                "chama": chama,
                "rules": rules,
                "about": about,
                "faqs": faqs,
            },
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def create_chama(request):
    if request.method == "POST":
        chama_name = request.POST.get("chama_name")
        chama_type = request.POST.get("chama_tags")
        no_limit = request.POST.get("noLimit")
        description = request.POST.get("description")
        registration_fee = request.POST.get("registration")
        last_joining_date = request.POST.get("last_joining_date")
        chama_category = request.POST.get("category")

        print(
            chama_name,
            chama_type,
            no_limit,
            description,
            registration_fee,
            last_joining_date,
            chama_category,
        )
        members_allowed = 0
        if no_limit == "noLimit":
            members_allowed = "infinite"
        else:
            members_allowed = request.POST.get("members_allowed")

        # Convert last and first to datetime objects and get current time
        last_joining_date = datetime.strptime(last_joining_date, "%Y-%m-%d")
        current_time_nairobi = datetime.now(nairobi_tz).replace(tzinfo=None)

        # check that last day of joining is >= today
        if last_joining_date.date() >= current_time_nairobi.date():
            data = {
                "chama_name": chama_name,
                "chama_type": chama_type,
                "description": description,
                "num_of_members_allowed": members_allowed,
                "registration_fee": registration_fee,
                "restart": False,
                "category": chama_category,
                "last_joining_date": last_joining_date.strftime("%Y-%m-%d %H:%M:%S"),
            }

            headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            }
            response = requests.post(
                f"{os.getenv('api_url')}/chamas",
                json=data,
                headers=headers,
            )

            if response.status_code == HTTPStatus.CREATED:
                messages.success(request, "Chama created successfully.")
                return redirect(reverse("manager:dashboard"))

        else:
            messages.error(request, "last joining date should not be in the past")
            return redirect(reverse("manager:dashboard"))

    return redirect(reverse("manager:dashboard"))


# it gets the one chama details and displays them
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def chama(request, key):
    # get the chama details
    chama_name = key
    chama_id = get_chama_id(chama_name)
    current_user = request.COOKIES.get("current_user")
    manager_id = get_user_id(current_user)
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    # ===================================
    urls = (
        (f"{os.getenv('api_url')}/chamas", {"chama_name": chama_name}),  # chama
        (
            f"{os.getenv('api_url')}/chamas/account_balance/{chama_id}",
            None,
        ),  # account_balance
        (f"{os.getenv('api_url')}/chamas/today_deposits/{chama_id}", None),
        (f"{os.getenv('api_url')}/transactions/{chama_name}", {"chama_id": chama_id}),
        (
            f"{os.getenv('api_url')}/investments/chamas/account_balance/{chama_id}",
            None,
        ),  # investment balance
        (
            f"{os.getenv('api_url')}/chamas/members_count/{chama_id}",
            None,
        ),  # members count
        (
            f"{os.getenv('api_url')}/investments/chamas/monthly_interests/{chama_id}",
            {"limit": 3},
        ),
        (f"{os.getenv('api_url')}/investments/chamas/recent_activity/{chama_id}", None),
        (f"{os.getenv('api_url')}/managers/profile_picture", None),
        (f"{os.getenv('api_url')}/investments/chamas/available_investments", None),
        (f"{os.getenv('api_url')}/investments/chamas/in-house_mmf", None),
    )
    # ===================================

    results = await chama_async(urls, headers)

    if results["chama"]:
        return render(
            request,
            "manager/chamadashboard.html",
            {
                "current_user": current_user,
                "manager_id": manager_id,
                "chama_name": chama_name,
                "chama": results["chama"],
                "investment_account": results["investment_account"],
                "investment_activity": results["investment_activity"],
                "mmf_withdrawal_activity": results["mmf_withdrawal_activity"],
                "fund_performance": results["fund_performance"],
                "recent_transactions": results["recent_activity"],
                "available_investments": results["available_investments"],
                "inhouse_mmf": results["inhouse_mmf"],
            },
        )
    else:
        return redirect(reverse("manager:dashboard"))


async def chama_async(urls, headers):
    results = {}

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = []
        for url, payload in urls:
            if payload:
                tasks.append(fetch_chama_data(session, url, results, data=payload))
            else:
                tasks.append(fetch_chama_data(session, url, results))

        await asyncio.gather(*tasks)

    chama = None
    recent_activity = []
    investment_data = {}
    mmf_withdrawal_activity = []
    fund_performance = None
    available_investments = None
    inhouse_mmf = None
    # append investment_balance, and account_balance
    if urls[0][0] in results and results[urls[0][0]]["status"] == 200:
        chama = results[urls[0][0]]["data"]["Chama"][0]
        if urls[1][0] in results and results[urls[1][0]]["status"] == 200:
            chama["account_balance"] = results[urls[1][0]]["data"]["account_balance"]
        if urls[2][0] in results and results[urls[2][0]]["status"] == 200:
            chama["today_deposits"] = results[urls[2][0]]["data"]["today_deposits"]
        if urls[3][0] in results and results[urls[3][0]]["status"] == 200:
            recent_activity = recent_transactions(results[urls[3][0]]["data"])
        if urls[4][0] in results and results[urls[4][0]]["status"] == 200:
            investment_data["investment_data_mmf"] = results[urls[4][0]]["data"]
        if urls[5][0] in results and results[urls[5][0]]["status"] == 200:
            chama["number_of_members"] = results[urls[5][0]]["data"][
                "number_of_members"
            ]
        if urls[6][0] in results and results[urls[6][0]]["status"] == 200:
            fund_performance = organise_monthly_performance(results[urls[6][0]]["data"])
        if urls[7][0] in results and results[urls[7][0]]["status"] == 200:
            investment_data["investment_activity"] = organise_investment_activity(
                results[urls[7][0]]["data"]["investment_activity"]
            )
            mmf_withdrawal_activity = organise_mmf_withdrawal_activity(
                results[urls[7][0]]["data"]["mmf_withdrawal_activity"]
            )
        if urls[8][0] in results and results[urls[8][0]]["status"] == 200:
            chama["manager_profile_picture"] = results[urls[8][0]]["data"]
        if urls[9][0] in results and results[urls[9][0]]["status"] == 200:
            available_investments = results[urls[9][0]]["data"]
        if urls[10][0] in results and results[urls[10][0]]["status"] == 200:
            inhouse_mmf = results[urls[10][0]]["data"]

    investment_account = (
        investment_data["investment_data_mmf"]
        if "investment_data_mmf" in investment_data
        else None
    )

    investment_activty = (
        investment_data["investment_activity"]
        if "investment_activity" in investment_data
        else None
    )
    return {
        "chama": chama,
        "recent_activity": recent_activity,
        "investment_account": investment_account,
        "investment_activity": investment_activty,
        "mmf_withdrawal_activity": mmf_withdrawal_activity,
        "fund_performance": fund_performance,
        "available_investments": available_investments,
        "inhouse_mmf": inhouse_mmf,
    }


def organise_monthly_performance(monthly_performance):
    monthly_interests = []
    for performance in monthly_performance:
        performance["month"] = datetime(
            performance["year"], performance["month"], 1
        ).strftime("%B")
        performance["interest_earned"] = f"Ksh: {(performance['interest_earned']):,.2f}"
        del performance["year"]
        monthly_interests.append(performance)

    return monthly_interests


def organise_investment_activity(investment_activity):
    organised_investment_activity = []
    for activity in investment_activity:
        activity["amount"] = f"Ksh: {activity['amount']}"
        activity["time"] = extract_date_time(activity["transaction_date"])["time"]
        activity["date"] = extract_date_time(activity["transaction_date"])["date"]
        if activity["transaction_type"] == "deposit":
            activity["transaction_type"] = "Invested"
        elif activity["transaction_type"] == "withdraw":
            activity["transaction_type"] = "Withdrew"
        del activity["transaction_date"]
        del activity["id"]
        del activity["current_int_rate"]
        organised_investment_activity.append(activity)

    return organised_investment_activity


@tokens_in_cookies()
@validate_and_refresh_token()
def profile(request, manager_id):
    full_profile = get_user_full_profile(manager_id)
    return render(request, "manager/profile.html", {"profile": full_profile})


# updating password from the profile page while logged in
@tokens_in_cookies()
@validate_and_refresh_token()
def change_password(request, manager_id):
    if request.method == "POST":
        role = request.POST.get("role")
        current_password = request.POST.get("password")
        new_password = request.POST.get("newpassword")
        confirm_password = request.POST.get("renewpassword")

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect(reverse(f"{role}:profile", args=[manager_id]))

        url = f"{os.getenv('api_url')}/users/{role}/change_password"
        data = {
            "user_id": manager_id,
            "old_password": current_password,
            "new_password": new_password,
        }
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get(f'{role}_access_token')}",
        }
        response = requests.put(url, json=data, headers=headers)

        if response.status_code == 201:
            messages.success(request, "Password changed successfully")
            return redirect(reverse(f"{role}:profile", args=[manager_id]))
        else:
            messages.error(
                request, "An error occurred or the current password is wrong"
            )
            return redirect(reverse(f"{role}:profile", args=[manager_id]))

    return redirect(reverse(f"{role}:profile", args=[manager_id]))


@tokens_in_cookies()
@validate_and_refresh_token()
def view_chama_members(request, chama_name):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    chama_id = get_chama_id(chama_name)
    chama_members = requests.get(
        f"{os.getenv('api_url')}/members_tracker/chama_members/{chama_id}",
        headers=headers,
    )
    print(chama_members.json())
    return render(
        request,
        "manager/view_members_list.html",
        {
            "chama_members": chama_members.json(),
            "chama_name": chama_name,
            "chama_id": chama_id,
        },
    )
