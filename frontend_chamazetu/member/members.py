import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from datetime import datetime, timedelta

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.chamas import get_chama_contribution_day, get_previous_contribution_date


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def get_member_recent_transactions(request):
    url = f"{config('api_url')}/members/recent_transactions"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        member_recent_transactions = response.json()
        return member_recent_transactions

    return None


def get_wallet_balance(request):
    url = f"{config('api_url')}/members/wallet_balance"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        wallet_balance = response.json()["wallet_balance"]
        return wallet_balance
    else:
        return None


def get_member_expected_contribution(member_id, chama_id):
    url = f"{config('api_url')}/members/expected_contribution"
    data = {"member_id": member_id, "chama_id": chama_id}
    resp = requests.get(url, json=data)
    if resp.status_code == 200:
        return resp.json()["member_expected_contribution"]
    return None


def get_user_id(role, email):
    url = f"{config('api_url')}/users/{role}/{email}"
    resp = requests.get(url)
    if resp.status_code == 200:
        user = resp.json()
        user_id = user["User_id"]
        return user_id
    return None


def get_user_full_name(role, id):
    url = f"{config('api_url')}/users/names/{role}/{id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        user = resp.json()
        full_name = f"{user['first_name']} {user['last_name']}"
        return full_name
    return None


def get_user_email(role, id):
    url = f"{config('api_url')}/users/email/{role}/{id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        user = resp.json()
        email = user["email"]
        return email
    return None


def get_user_phone_number(role, id):
    url = f"{config('api_url')}/users/phone_number/{role}/{id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        user = resp.json()
        phone_number = user["phone_number"]
        return phone_number
    return None


def get_user_full_profile(role, id):
    url = f"{config('api_url')}/users/full_profile/{role}/{id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        user = resp.json()
        return user
    return None


def get_member_contribution_so_far(chama_id, member_id):
    upcoming_contribution_datetime = get_chama_contribution_day(chama_id)[
        "contribution_date"
    ]
    upcoming_contribution_date = (
        datetime.strptime(upcoming_contribution_datetime, "%d-%B-%Y")
    ).strftime("%d-%m-%Y")
    previous_contribution_date = get_previous_contribution_date(chama_id)

    data = {
        "chama_id": chama_id,
        "member_id": member_id,
        "upcoming_contribution_date": upcoming_contribution_date,
        "previous_contribution_date": previous_contribution_date,
    }
    resp = requests.get(
        f"{config('api_url')}/members/member_contribution_so_far", json=data
    )
    if resp.status_code == 200:
        return resp.json()["member_contribution"]

    return 0
