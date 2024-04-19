import requests, jwt, json, threading
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_data
from chama.chamas import get_chama_name
from .members import get_member_recent_transactions, get_user_id
from .date_day_time import extract_date_time

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def dashboard(request):
    # backend validation of token
    current_user = request.COOKIES.get("current_member")
    member_id = get_user_id("member", current_user)

    # TODO: replace this with a call to the backend
    # get the current users id
    try:
        query = "SELECT id FROM members WHERE email = %s"
        params = [current_user]
        member_id = (execute_sql(query, params))[0][0]
        # use the id to get the chama the user is in from the associate table
        query = "SELECT chama_id FROM members_chamas WHERE member_id = %s"
        params = [member_id]
        chama_ids = execute_sql(query, params)
    except Exception as e:
        print(e)
        chama_ids = None

    chamas_gen = (chama[0] for chama in chama_ids)
    chama_ids = list(chamas_gen)

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    urls = [
        (f"{config('api_url')}/chamas/my_chamas", {"chamaids": chama_ids}),
        (f"{config('api_url')}/members/recent_transactions", {"member_id": member_id}),
        (f"{config('api_url')}/members/wallet_balance", {}),
        (f"{config('api_url')}/members/recent_wallet_activity", {}),
    ]

    results = member_dashboard_threads(urls, headers)
    print("=========================")

    if results["chamas"]:
        return render(
            request,
            "member/dashboard.html",
            {
                "current_user": {"current_user": current_user, "member_id": member_id},
                "chamas": results["chamas"],
                "my_recent_transactions": results["member_recent_transactions"],
                "wallet_activity": results["wallet_activity"],
            },
        )
    else:
        return render(request, "member/dashboard.html")


def member_dashboard_threads(urls, headers):
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

    for thread in threads:
        thread.join()

    chamas = None
    member_recent_transactions = None
    wallet_activity = {}
    new_products_features = None

    if results[urls[0][0]]["status"] == 200:
        chamas = results[urls[0][0]]["data"]["Chama"]
        if urls[1][0] in results and results[urls[1][0]]["status"] == 200:
            member_recent_transactions = organise_members_recent_transactions(
                results[urls[1][0]]["data"]
            )
        if urls[2][0] in results and results[urls[2][0]]["status"] == 200:
            wallet_activity = results[urls[2][0]]["data"]
        if urls[3][0] in results and results[urls[3][0]]["status"] == 200:
            wallet_activity["recent_wallet_activity"] = organise_wallet_activity(
                results[urls[3][0]]["data"]
            )

    return {
        "chamas": chamas,
        "member_recent_transactions": member_recent_transactions,
        "wallet_activity": wallet_activity,
    }


def organise_members_recent_transactions(recent_transactions):
    for transaction in recent_transactions:
        transaction["chama_name"] = get_chama_name(transaction["chama_id"])
        transaction["amount"] = f"Ksh {transaction['amount']}"
        transaction["date"] = extract_date_time(transaction["date_of_transaction"])[
            "date"
        ]
        transaction["time"] = extract_date_time(transaction["date_of_transaction"])[
            "time"
        ]
        if transaction["transaction_completed"] == True:
            transaction["status"] = "Completed"
        else:
            transaction["status"] = "not completed"

    return recent_transactions


def organise_wallet_activity(wallet_activity):
    for activity in wallet_activity:
        activity["amount"] = f"Ksh: {activity['amount']}"
        activity["date"] = extract_date_time(activity["transaction_date"])["date"]
        activity["time"] = extract_date_time(activity["transaction_date"])["time"]
        if activity["transaction_completed"] == True:
            activity["status"] = "Completed"
        else:
            activity["status"] = "not completed"
        activity["transaction_type"] = (activity["transaction_type"]).replace("_", " ")

    return wallet_activity


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def profile(request, role="member"):
    page = f"member/profile.html"
    return render(request, page)


def is_empty_dict(data):
    return isinstance(data, dict) and len(data) == 0
