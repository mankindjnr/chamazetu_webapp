import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.contrib import messages
from datetime import datetime

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_data
from chama.chamas import get_chama_id, get_chama_number_of_members
from member.member_chama import (
    access_chama_threads,
    recent_transactions,
    chama_details_organised,
)
from member.members import get_user_full_profile, get_user_id
from member.membermanagement import is_empty_dict
from member.date_day_time import extract_date_time
from chama.tasks import update_contribution_days


from chama.usermanagement import (
    validate_token,
    refresh_token,
)

load_dotenv()


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def dashboard(request):
    current_user = request.COOKIES.get("current_manager")
    # get the id of the current mananger
    manager_id = get_user_id("manager", current_user)

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
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

    return {
        "chamas": chamas,
        "updates_and_features": updates_and_features,
        "profile_picture": profile_picture,
    }


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def get_about_chama(request, chama_name):
    chama_id = get_chama_id(chama_name)
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
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
        print(chama_data.status_code)
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def create_chama(request):
    if request.method == "POST":
        chama_name = request.POST.get("chama_name")
        chama_type = request.POST.get("chama_type")
        no_limit = request.POST.get("noLimit")
        description = request.POST.get("description")
        accepting_members = request.POST.get("accepting_members")
        registration_fee = request.POST.get("registration")
        share_price = request.POST.get("share_price")
        contribution_frequency = request.POST.get("frequency")
        start_date = request.POST.get("start_date")

        chama_category = request.POST.get("category")
        fine = request.POST.get("fine_per_share")

        # check if the start_date > today and should be a atleast a week away from  today, the creation date
        # check if start_date < contribution day - calculate the contribution date - do this by creating a calculate the first contribution date function

        members_allowed = 0
        if no_limit == "on":
            members_allowed = "infinite"
        else:
            members_allowed = request.POST.get("members_allowed")

        contribution_day = "daily"
        if contribution_frequency == "weekly":
            contribution_day = request.POST.get("weekly_day")
        elif contribution_frequency == "monthly":
            contribution_day = request.POST.get("monthly_day")

        if accepting_members == "on":
            is_active = True
            accepting_members = True
        else:
            accepting_members = False
        # check if start_date is less than end_date and if start date is today and change the is_active to True

        chama_manager = request.COOKIES.get("current_manager")
        manager_id = get_user_id("manager", chama_manager)

        # Convert start_date and end_date to datetime objects and get current time
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

        data = {
            "chama_name": chama_name,
            "chama_type": chama_type,
            "description": description,
            "num_of_members_allowed": members_allowed,
            "accepting_members": accepting_members,
            "registration_fee": registration_fee,
            "contribution_amount": share_price,
            "contribution_interval": contribution_frequency,
            "contribution_day": contribution_day,
            "start_cycle": start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "restart": False,
            "is_active": is_active,
            "manager_id": manager_id,
            "category": chama_category,
            "fine_per_share": fine,
        }

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        response = requests.post(
            f"{os.getenv('api_url')}/chamas",
            json=data,
            headers=headers,
        )

        if response.status_code == 201:
            update_contribution_days.delay()  # this will be replaced with a set contribution date background task it will take, interval and start cycle dates
            messages.success(request, "Chama created successfully.")
            return redirect(reverse("manager:dashboard"))

    return redirect(reverse("manager:dashboard"))


# it gets the one chama details and displays them
@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def chama(request, key):
    # get the chama details
    chama_name = key
    chama_id = get_chama_id(chama_name)
    current_user = request.COOKIES.get("current_manager")
    manager_id = get_user_id("manager", current_user)
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
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
        (f"{os.getenv('api_url')}/managers/profile_picture", {}),
    )
    # ===================================

    results = chama_threads(urls, headers)

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
                "fund_performance": results["fund_performance"],
                "recent_transactions": results["recent_activity"],
            },
        )
    else:
        return redirect(reverse("manager:dashboard"))


def chama_threads(urls, headers):
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

    chama = None
    recent_activity = []
    investment_data = {}
    fund_performance = None
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
                results[urls[7][0]]["data"]
            )
        if urls[8][0] in results and results[urls[8][0]]["status"] == 200:
            chama["manager_profile_picture"] = results[urls[8][0]]["data"]

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
        "fund_performance": fund_performance,
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


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def profile(request, manager_id):
    full_profile = get_user_full_profile("manager", manager_id)
    return render(request, "manager/profile.html", {"profile": full_profile})


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
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


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def view_chama_members(request, chama_name):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
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
