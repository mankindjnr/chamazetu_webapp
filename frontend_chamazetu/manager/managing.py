import requests, jwt, json, threading
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from django.contrib import messages
from datetime import datetime

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_data
from chama.chamas import get_chama_id
from member.member_chama import access_chama_threads, recent_transactions


from chama.usermanagement import (
    validate_token,
    refresh_token,
)


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def dashboard(request):
    current_user = request.COOKIES.get("current_manager")

    # get the id of the current mananger
    query = "SELECT id FROM managers WHERE email = %s"
    params = [current_user]
    manager_id = (execute_sql(query, params))[0][0]

    # get the chamas connected to id of the current user
    query = "SELECT chama_name, is_active FROM chamas WHERE manager_id = %s"
    params = [manager_id]
    chamas = execute_sql(query, params)

    chamas = dict(chamas)
    print(chamas)
    print()
    return render(
        request,
        "manager/dashboard.html",
        {
            "current_user": current_user,
            "chamas": chamas,
        },
    )


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
            accepting_members = True
        else:
            accepting_members = False
        # check if start_date is less than end_date and if start date is today and change the is_active to True

        chama_manager = request.COOKIES.get("current_manager")

        query = "SELECT id FROM managers WHERE email = %s"
        params = [chama_manager]
        manager_id = (execute_sql(query, params))[0][0]

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
            "manager_id": manager_id,
        }
        print("nolimit", no_limit)
        print("members_allowed", members_allowed)
        print("--------------create chama details---------------")
        print(data)

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        response = requests.post(
            f"{config('api_url')}/chamas",
            json=data,
            headers=headers,
        )
        print("---------chama creation response---------")
        print(response.status_code)
        print()
        print(response)

        if response.status_code == 201:
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
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
    }

    # ===================================
    urls = (
        (f"{config('api_url')}/chamas", {"chama_name": chama_name}),  # chama
        (
            f"{config('api_url')}/chamas/account_balance/{chama_id}",
            None,
        ),  # account_balance
        (f"{config('api_url')}/chamas/today_deposits/{chama_id}", None),
        (f"{config('api_url')}/transactions/{chama_name}", {"chama_id": chama_id}),
        (
            f"{config('api_url')}/investments/chamas/account_balance/{chama_id}",
            None,
        ),  # investment balance
    )
    # ===================================

    results = chama_threads(urls, headers)
    print("===========results thread=============")

    if results["chama"]:
        return render(
            request,
            "manager/chamadashboard.html",
            {
                "current_user": current_user,
                "chama_name": chama_name,
                "chama": results["chama"],
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
        else:
            thread = threading.Thread(target=fetch_data, args=(url, results))

        threads.append(thread)
        thread.start()

    # wait for all threads to finish
    for thread in threads:
        thread.join()

    chama = None
    recent_activity = []
    # append investment_balance, and account_balance
    if results[urls[0][0]]["status"] == 200:
        chama = results[urls[0][0]]["data"]["Chama"][0]
        if results[urls[1][0]]["status"] == 200:
            chama["account_balance"] = results[urls[1][0]]["data"]["account_balance"]
        if results[urls[2][0]]["status"] == 200:
            chama["today_deposits"] = results[urls[2][0]]["data"]["today_deposits"]
        if results[urls[3][0]]["status"] == 200:
            recent_activity = recent_transactions(results[urls[3][0]]["data"])
        if results[urls[4][0]]["status"] == 200:
            chama["investment_balance"] = results[urls[4][0]]["data"]["amount_invested"]

    return {"chama": chama, "recent_activity": recent_activity}


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def profile(request, role="manager"):
    page = f"manager/profile.html"
    return render(request, page)


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def chama_join_status(request):
    print("---------chama join path---------")
    print(request.path)
    if request.method == "POST":
        chama_name = request.POST.get("chama_name")
        status = request.POST.get("accepting_members")

        print()
        print(chama_name)
        print(status)
        if status == "on":
            status = True
        else:
            status = False

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        data = {"chama_name": chama_name, "accepting_members": status}
        print()
        print(data)
        response = requests.put(
            "http://chamazetu_backend:9400/chamas/join_status",
            json=data,
            headers=headers,
        )

        return redirect(reverse("manager:dashboard"))
    else:
        return redirect(reverse("manager:dashboard"))


def restart_pause_stop_chama(request):
    pass
