import requests, jwt, json, threading
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from django.contrib import messages
from collections import defaultdict

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.chamas import get_chama_id, get_chama_contribution_day
from chama.thread_urls import fetch_data
from .date_day_time import get_sunday_date, extract_date_time
from .membermanagement import (
    get_user_full_name,
    get_user_id,
    get_member_expected_contribution,
)
from .tasks import update_shares_number_for_member
from chama.tasks import update_contribution_days

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


# viewing a chamas in the public dashboard where users can join
@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def view_chama(request, chamaid):
    data = {"chamaid": chamaid}
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }
    resp = requests.get(f"{config('api_url')}/chamas/chama", json=data, headers=headers)
    if resp.status_code == 200:
        chama = resp.json()["Chama"][0]

        return render(
            request,
            "chama/blog_chama.html",
            {
                "role": "member",
                "chama": chama,
            },
        )


# viewing a chamas in the member dashboard where they can interact with specifc chama
@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def access_chama(request, chamaname):
    chama_id = get_chama_id(chamaname)
    chama_members_id = requests.get(f"{config('api_url')}/chamas/members/{chama_id}")

    urls = [
        (f"{config('api_url')}/chamas/chama_name", {"chamaname": chamaname}),
        (
            f"{config('api_url')}/transactions/{chamaname}",
            {"chama_id": chama_id},
        ),  # recent transactions
        (
            f"{config('api_url')}/transactions/{chamaname}/members",
            {
                "chama_id": chama_id,
                "members_ids": chama_members_id.json()["Members"],
                "date_of_transaction": get_sunday_date().strftime("%Y-%m-%d"),
            },
        ),  # chama weekly activity
        (f"{config('api_url')}/chamas/account_balance/{chama_id}", None),
        (f"{config('api_url')}/chamas/today_deposits/{chama_id}", None),
        (f"{config('api_url')}/investments/chamas/account_balance/{chama_id}", None),
        (f"{config('api_url')}/investments/chamas/recent_activity/{chama_id}", None),
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
                "current_user": request.COOKIES.get("current_member"),
                "role": "member",
                "chama": results.get("chama"),
                "recent_transactions": results.get("recent_transactions"),
                "activity": results.get("activity"),
                "investment_activity": results.get("investment_activity"),
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
    members_weekly_transactions = []

    # process the results of the threads
    if results[urls[0][0]]["status"] == 200:
        chama = results[urls[0][0]]["data"]["Chama"][0]
        chama_id = get_chama_id(chama["chama_name"])
        chama["chama_day"] = get_chama_contribution_day(chama_id)
        if results[urls[1][0]]["status"] == 200:
            if len(results[urls[1][0]]["data"]) > 0:
                recent_activity = recent_transactions(results[urls[1][0]]["data"])
        if results[urls[2][0]]["status"] == 200:
            members_weekly_transactions = chama_weekly_contribution_activity(
                results[urls[2][0]]["data"], chama_id
            )
        if results[urls[3][0]]["status"] == 200:
            chama["account_balance"] = results[urls[3][0]]["data"]["account_balance"]
        if results[urls[4][0]]["status"] == 200:
            chama["today_deposits"] = results[urls[4][0]]["data"]["today_deposits"]
        if results[urls[5][0]]["status"] == 200:
            chama["investment_balance"] = results[urls[5][0]]["data"]["amount_invested"]
        if results[urls[6][0]]["status"] == 200:
            investment_activity = investment_activities(results[urls[6][0]]["data"])

    # return the processed results chama, transactions, members
    return {
        "chama": chama,
        "recent_transactions": recent_activity,
        "activity": members_weekly_transactions,
        "investment_activity": investment_activity,
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

    print("=====================================")
    print(weekly_activity)

    return weekly_activity


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
            f"{config('api_url')}/chamas/join", json=data, headers=headers
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
