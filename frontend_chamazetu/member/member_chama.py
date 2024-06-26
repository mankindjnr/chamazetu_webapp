import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, date
from django.contrib import messages
from collections import defaultdict

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.chamas import (
    get_chama_id,
    get_chama_contribution_day,
    get_previous_contribution_date,
    public_chama_threads,
)
from chama.thread_urls import fetch_data
from .date_day_time import get_sunday_date, extract_date_time
from .members import (
    get_member_expected_contribution,
    get_user_full_name,
    get_user_id,
    get_member_contribution_so_far,
    get_user_full_profile,
)
from manager.managers import get_manager_profile_picture
from .membermanagement import is_empty_dict
from .tasks import update_shares_number_for_member, calculate_missed_contributions_fines
from chama.tasks import update_contribution_days

from chama.usermanagement import (
    validate_token,
    refresh_token,
)

load_dotenv()


# viewing a chamas in the public dashboard where users can join
@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def view_chama(request, chamaid):
    data = {"chamaid": chamaid}
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    urls = [
        (f"{os.getenv('api_url')}/chamas/public_chama/{chamaid}", None),
        (f"{os.getenv('api_url')}/chamas/faqs/{chamaid}", None),
        (f"{os.getenv('api_url')}/chamas/rules/{chamaid}", None),
        (f"{os.getenv('api_url')}/chamas/mission/vision/{chamaid}", None),
    ]

    results = public_chama_threads(urls)

    # resp = requests.get(f"{os.getenv('api_url')}/chamas/public_chama", json=data)
    if results["public_chama"]:
        manager_profile = get_user_full_profile(
            "manager", results["public_chama"]["manager_id"]
        )

        # print(chama)

        return render(
            request,
            "chama/blog_chama.html",
            {
                "role": "member" if headers else None,
                "chama": results["public_chama"],
                "manager": manager_profile,
                "faqs": results["faqs"],
                "rules": results["rules"],
                "mission": results["mission"],
                "vision": results["vision"],
            },
        )


# viewing a chamas in the member dashboard where they can interact with specifc chama
@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def access_chama(request, chamaname):
    chama_id = get_chama_id(chamaname)
    chama_members_id = requests.get(f"{os.getenv('api_url')}/chamas/members/{chama_id}")
    current_user = request.COOKIES.get("current_member")
    role = "member"

    urls = [
        (f"{os.getenv('api_url')}/chamas/chama_name", {"chamaname": chamaname}),
        (
            f"{os.getenv('api_url')}/transactions/{chamaname}",
            {"chama_id": chama_id},
        ),  # recent transactions
        (
            f"{os.getenv('api_url')}/transactions/{chamaname}/members",
            {
                "chama_id": chama_id,
                "members_ids": chama_members_id.json()["Members"],
                "date_of_transaction": get_sunday_date().strftime("%Y-%m-%d"),
            },
        ),  # chama weekly activity
        (f"{os.getenv('api_url')}/chamas/account_balance/{chama_id}", None),
        (f"{os.getenv('api_url')}/chamas/today_deposits/{chama_id}", None),
        (f"{os.getenv('api_url')}/investments/chamas/account_balance/{chama_id}", None),
        (f"{os.getenv('api_url')}/investments/chamas/recent_activity/{chama_id}", None),
        (f"{os.getenv('api_url')}/members/wallet_balance", {}),
        (f"{os.getenv('api_url')}/users/{role}/{current_user}", None),
        (
            f"{os.getenv('api_url')}/investments/chamas/monthly_interests/{chama_id}",
            {"limit": 3},
        ),
        (f"{os.getenv('api_url')}/chamas/fines/{chama_id}", None),
    ]

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    results = access_chama_threads(urls, headers)

    if results.get("chama"):
        return render(
            request,
            "member/chamadashboard.html",
            {
                "current_user": {
                    "current_user": current_user,
                    "member_id": results.get("wallet")["member_id"],
                },
                "role": "member",
                "chama": results.get("chama"),
                "recent_transactions": results.get("recent_transactions"),
                "activity": results.get("activity"),
                "investment_activity": results.get("investment_activity"),
                "mmf_withdrawal_activity": results.get("mmf_withdrawal_activity"),
                "fines": results.get("fines"),
                "fund_performance": results.get("monthly_interests"),
                "investment_data": results.get("investment_data"),
                "wallet": results.get("wallet"),
                "user_profile": results.get("user_profile"),
            },
        )
    else:
        messages.error(request, "Failed to access chama, try again later")
        return HttpResponseRedirect(reverse("member:dashboard"))


def access_chama_threads(urls, headers):
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
    investment_activity = []
    mmf_withdrawal_activity = []
    members_weekly_transactions = []
    wallet = []
    monthly_interests = None
    user_profile = {}
    investment_data = None
    fines = None

    # process the results of the threads
    if results[urls[0][0]]["status"] == 200:
        chama = results[urls[0][0]]["data"]["Chama"][0]
        chama_id = get_chama_id(chama["chama_name"])
        contribution_day_details = get_chama_contribution_day(chama_id)
        chama["contribution_day"] = contribution_day_details["contribution_day"]
        chama["contribution_date"] = contribution_day_details["contribution_date"]

        if urls[1][0] in results and results[urls[1][0]]["status"] == 200:
            if len(results[urls[1][0]]["data"]) > 0:
                recent_activity = recent_transactions(results[urls[1][0]]["data"])
        if urls[2][0] in results and results[urls[2][0]]["status"] == 200:
            members_weekly_transactions = chama_weekly_contribution_activity(
                results[urls[2][0]]["data"], chama_id
            )
        if urls[3][0] in results and results[urls[3][0]]["status"] == 200:
            chama["account_balance"] = results[urls[3][0]]["data"]["account_balance"]
        if urls[4][0] in results and results[urls[4][0]]["status"] == 200:
            chama["today_deposits"] = results[urls[4][0]]["data"]["today_deposits"]
        if urls[5][0] in results and results[urls[5][0]]["status"] == 200:
            investment_data = results[urls[5][0]]["data"]
        if urls[6][0] in results and results[urls[6][0]]["status"] == 200:
            investment_activity = investment_activities(
                results[urls[6][0]]["data"]["investment_activity"]
            )
            mmf_withdrawal_activity = organise_mmf_withdrawal_activity(
                results[urls[6][0]]["data"]["mmf_withdrawal_activity"]
            )
        if urls[7][0] in results and results[urls[7][0]]["status"] == 200:
            wallet = results[urls[7][0]]["data"]
        if urls[8][0] in results and results[urls[8][0]]["status"] == 200:
            wallet["member_id"] = results[urls[8][0]]["data"]["User_id"]
            wallet["profile_image"] = (
                results[urls[8][0]]["data"]["profile_picture"]
                if "profile_picture" in results[urls[8][0]]["data"]
                else ""
            )
        if urls[9][0] in results and results[urls[9][0]]["status"] == 200:
            monthly_interests = organise_monthly_performance(
                results[urls[9][0]]["data"]
            )
        if urls[10][0] in results and results[urls[10][0]]["status"] == 200:
            fines = organise_fines(results[urls[10][0]]["data"]["fines"])

    # return the processed results chama, transactions, members
    user_profile["profile_image"] = wallet["profile_image"]
    return {
        "chama": chama,
        "recent_transactions": recent_activity,
        "activity": members_weekly_transactions,
        "investment_activity": investment_activity,
        "mmf_withdrawal_activity": mmf_withdrawal_activity,
        "monthly_interests": monthly_interests,
        "investment_data": investment_data,
        "wallet": wallet,
        "user_profile": user_profile,
        "fines": fines,
    }


# recent transactions for a chama updating date and time
def recent_transactions(transactions):
    recent_transactions = []
    for transaction in transactions:
        transaction["time"] = extract_date_time(transaction["date_of_transaction"])[
            "time"
        ]
        transaction["date"] = extract_date_time(transaction["date_of_transaction"])[
            "date"
        ]
        transaction["member_name"] = get_user_full_name(
            "member", transaction["member_id"]
        )
        recent_transactions.append(transaction)

        if len(recent_transactions) == 5:
            break

    return recent_transactions


def investment_activities(activities):
    invst_activity = []
    for activity in activities:
        activity["time"] = extract_date_time(activity["transaction_date"])["time"]
        activity["date"] = extract_date_time(activity["transaction_date"])["date"]
        invst_activity.append(activity)

        if len(invst_activity) == 5:
            break

    return invst_activity


def organise_mmf_withdrawal_activity(withdrawal_activity):
    organised_withdrawal_activity = []
    for activity in withdrawal_activity:
        activity["amount"] = f"Ksh: {activity['amount']}"
        activity["time"] = extract_date_time(activity["withdrawal_date"])["time"]
        activity["date"] = extract_date_time(activity["withdrawal_date"])["date"]
        del activity["withdrawal_date"]
        del activity["id"]
        del activity["chama_id"]
        organised_withdrawal_activity.append(activity)

    return organised_withdrawal_activity


# retrieve members weekly transactions and arrange them by membe and daily transactions amount
def chama_weekly_contribution_activity(members_weekly_transactions, chama_id):
    members_daily_transactions = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    for key, value in members_weekly_transactions.items():
        member_name = get_user_full_name("member", key)
        for item in value:
            day = extract_date_time(item["date_of_transaction"])["day"]
            amount = item["amount"]
            members_daily_transactions[member_name][key][day] += amount

    chama_weekly_activity = organise_activity(members_daily_transactions, chama_id)

    return chama_weekly_activity


# organise the weekly transactions by member and every day of the week
def organise_activity(members_daily_transactions, chama_id):
    days = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    for member_name, member_transactions in members_daily_transactions.items():
        for member_id, daily_transactions in member_transactions.items():
            for day in days:
                if day not in daily_transactions:
                    daily_transactions[day] = 0

    weekly_activity = []
    for member_name, member_transactions in members_daily_transactions.items():
        for member_id, daily_transactions in member_transactions.items():
            member_activity = {"member_name": member_name, "member_id": member_id}
            # add the daily transactions and their amounts to the member_activity dictionary as key value pairs in order of the days of the week (Sunday to Saturday)
            for day in days:
                member_activity[day] = daily_transactions[day]

            weekly_activity.append(member_activity)

    # TODO: make it a bg task and listen for the task to finish then using js update the page
    for activity in weekly_activity:
        activity["expected_contribution"] = get_member_expected_contribution(
            activity["member_id"], chama_id
        )
        activity["member_contribution_so_far"] = get_member_contribution_so_far(
            chama_id, activity["member_id"]
        )

    return weekly_activity


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


def organise_fines(fines):
    fines_organised = []
    for fine in fines:
        fine["member_name"] = get_user_full_name("member", fine["member_id"])
        fine["fine"] = f"Ksh: {fine['fine']}"
        fine["total_expected_amount"] = f"Ksh: {fine['total_expected_amount']}"
        del fine["member_id"]
        fines_organised.append(fine)

    return fines_organised


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def join_chama(request):
    if request.method == "POST":
        data = {
            "chamaname": request.POST.get("chamaname"),
            "num_of_shares": request.POST.get("shares_num"),
        }
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }
        resp = requests.post(
            f"{os.getenv('api_url')}/chamas/join", json=data, headers=headers
        )
        if resp.status_code == 201:
            update_shares_number_for_member.delay(
                get_chama_id(data["chamaname"]), data["num_of_shares"], headers
            )
            return HttpResponseRedirect(reverse("member:dashboard"))
        elif resp.status_code == 400:
            messages.error(request, f"you are already a member of {data['chamaname']}")
            return HttpResponseRedirect(
                reverse("chama:chamas", args={"role": "member"})
            )
        else:
            messages.error(request, "Failed to join chama")
            chama_id = get_chama_id(request.POST.get("chamaname"))
            return HttpResponseRedirect(
                reverse("chama:chamas", args={"role": "member"})
            )

    return HttpResponseRedirect(reverse("chama:chamas", args={"role": "member"}))


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def view_chama_members(request, chama_name):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    chama_id = get_chama_id(chama_name)
    chama_members = requests.get(
        f"{os.getenv('api_url')}/members_tracker/chama_members/{chama_id}",
        headers=headers,
    )
    print(chama_members.json())
    return render(
        request,
        "member/list_members.html",
        {
            "chama_members": chama_members.json(),
            "chama_name": chama_name,
        },
    )


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def get_about_chama(request, chama_name):
    chama_id = get_chama_id(chama_name)
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }
    chama_data = requests.get(
        f"{os.getenv('api_url')}/chamas/about_chama/{chama_id}",
        headers=headers,
    )
    print("===================about================")
    if chama_data.status_code == 200:
        chama = chama_details_organised(chama_data.json().get("chama"))
        rules = chama_data.json().get("rules")
        about = chama_data.json().get("about")
        faqs = chama_data.json().get("faqs")

        return render(
            request,
            "chama/about_chama.html",
            {
                "role": "member",
                "chama": chama,
                "rules": rules,
                "about": about,
                "faqs": faqs,
            },
        )
    else:
        print(chama_data.status_code)
        return redirect(reverse("member:dashboard"))


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
    chama_details["contribution_amount"] = (
        f"Ksh: {(chama_details['contribution_amount']):,.2f}"
    )
    chama_details["contribution_interval"] = chama_details[
        "contribution_interval"
    ].capitalize()
    chama_details["contribution_day"] = chama_details["contribution_day"].capitalize()
    # chama_details["fine_per_share"] = f"Ksh: {(chama_details['fine_per_share']):,.2f}"
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
