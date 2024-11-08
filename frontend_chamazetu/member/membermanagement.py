import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import  HttpResponseRedirect, HttpResponse, JsonResponse, HttpResponseServerError
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.contrib import messages
from http import HTTPStatus

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_data
from chama.chamas import get_chama_name, get_chama_from_activity_id
from .members import (
    get_member_recent_transactions,
    get_user_id,
    get_user_full_name,
    get_user_phone_number,
    get_user_email,
    get_user_full_profile,
)
from .date_day_time import extract_date_time

from chama.usermanagement import (
    validate_token,
    refresh_token,
    check_token_validity,
)

load_dotenv()


@tokens_in_cookies()
@validate_and_refresh_token()
def dashboard(request):
    current_user = request.COOKIES.get("current_user")
    current_role = request.COOKIES.get("current_role")
    user_id = int(get_user_id(current_user))
    print("===========member dashboard================")
    # print(current_user, ":", current_role, ":", user_id)

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.get(f"{os.getenv('api_url')}/members/dashboard", headers=headers)

    if resp.status_code == HTTPStatus.OK:
        dashboard_data = resp.json()
        print("=======dashboard success=========")
        print(dashboard_data["wallet_transfers"])
        return render(
            request,
            "member/dashboard.html",
            {
                "current_role": current_role,
                "current_user": {"current_user": current_user, "user_id": user_id},
                "chamas": dashboard_data["member_chamas"],
                "my_recent_transactions": dashboard_data["recent_transactions"],
                "sent_transactions": dashboard_data["sent_transactions"],
                "wallet_transfers": dashboard_data["wallet_transfers"],
                "wallet_id": dashboard_data["wallet_id"],
                "wallet_balance": dashboard_data["wallet_balance"],
                "zetucoins": dashboard_data["zetucoins"],
                "recent_wallet_activity": dashboard_data["wallet_transactions"],
                "profile_picture": dashboard_data["profile_picture"],
            },
        )
    else:
        print("=======dashboard failed=========")
        return render(
            request,
            "member/dashboard.html",
            {
                "current_role": current_role,
                "current_user": {"current_user": current_user, "user_id": user_id},
            },
        )

    return reverse(f"{current_role}:dashboard")


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
    user_profile = {}

    if results[urls[0][0]]["status"] == 200:
        chamas = results[urls[0][0]]["data"]
        if urls[1][0] in results and results[urls[1][0]]["status"] == 200:
            member_recent_transactions = organise_members_recent_transactions(
                results[urls[1][0]]["data"]
            )
        if urls[2][0] in results and results[urls[2][0]]["status"] == 200:
            wallet_activity = results[urls[2][0]]["data"]
    # TODO: check if pulling them backwards causes issues with new members with 0 chamas
    if urls[3][0] in results and results[urls[3][0]]["status"] == 200:
        wallet_activity["recent_wallet_activity"] = organise_wallet_activity(
            results[urls[3][0]]["data"]
        )
    if urls[4][0] in results and results[urls[4][0]]["status"] == 200:
        user_profile["profile_image"] = results[urls[4][0]]["data"]["profile_picture"]

    return {
        "chamas": chamas,
        "member_recent_transactions": member_recent_transactions,
        "wallet_activity": wallet_activity,
        "user_profile": user_profile,
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


# updating password while logged in from profile page
@tokens_in_cookies()
@validate_and_refresh_token()
def change_password(request, user_id):
    if request.method == "POST":
        current_password = request.POST.get("password")
        new_password = request.POST.get("newpassword")
        confirm_password = request.POST.get("renewpassword")
        role = request.COOKIES.get("current_role")

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect(reverse("member:profile", args=[user_id]))

        url = f"{os.getenv('api_url')}/users/change_password"
        data = {
            "user_id": user_id,
            "old_password": current_password,
            "new_password": new_password,
        }
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        response = requests.put(url, json=data, headers=headers)

        if response.status_code == HTTPStatus.CREATED:
            messages.success(request, "Password changed successfully")
            return redirect(reverse("member:profile", args=[user_id]))
        else:
            messages.error(
                request, "An error occurred or the current password is wrong"
            )
            return redirect(reverse("member:profile", args=[user_id]))

    return redirect(reverse("member:profile", args=[user_id]))


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def profile(request, user_id):
    full_profile = get_user_full_profile(user_id)
    print("===========member profile================")
    print(full_profile)
    current_role = request.COOKIES.get("current_role")
    return render(
        request,
        "member/profile.html",
        {
            "user_id": user_id,
            "profile": full_profile,
            "current_role": current_role,
        },
    )


def is_empty_dict(data):
    return isinstance(data, dict) and len(data) == 0


# the invite link function
# this is the function that users will be directed to after receiving an invite link, it should make users signin and to the chama or activity they were invited to
# the function will check if the user is already signed in, if they are, it will redirect them to the chama or activity they were invited to
def process_invite(request, invite_to, name, id):
    access_token = request.COOKIES.get("access_token")
    refresh_token = request.COOKIES.get("refresh_token")

    if access_token and refresh_token:
        # check if the user is already signed in
        try:
            check_token_validity(access_token)
            if invite_to == "chama":
                return redirect(reverse("member:view_private_chama", args=[id]))
            else:
                chama_name, chama_id = get_chama_from_activity_id(id)
                return redirect(
                    reverse("member:chama_activities", args=[chama_name, chama_id])
                )
        except (ExpiredSignatureError, InvalidTokenError, Exception) as e:
            if invite_to == "chama":
                request.session["post_login_redirect"] = reverse(
                    "member:view_private_chama", args=[id]
                )
            else:
                chama_name, chama_id = get_chama_from_activity_id(id)
                request.session["post_login_redirect"] = reverse(
                    "member:chama_activities", args=[chama_name, chama_id]
                )
    else:
        if invite_to == "chama":
            request.session["post_login_redirect"] = reverse(
                "member:view_private_chama", args=[id]
            )
        else:
            chama_name, chama_id = get_chama_from_activity_id(id)
            request.session["post_login_redirect"] = reverse(
                "member:chama_activities", args=[chama_name, chama_id]
            )

    return redirect(reverse("chama:signin"))

def self_service(request):
    url = f"{os.getenv('api_url')}/members/self_service_transactions"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    response = requests.get(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        return render(request, "member/self_service.html", {"transactions": response.json()["incomplete_deposits"]})
    else:
        messages.error(request, "An error occurred, please try again later")

    referer = request.META.get("HTTP_REFERER", "member:dashboard")
    return HttpResponseRedirect(referer)