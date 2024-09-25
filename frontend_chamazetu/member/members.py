import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta
from http import HTTPStatus

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.chamas import get_chama_contribution_day, get_previous_contribution_date

load_dotenv()


@tokens_in_cookies()
@validate_and_refresh_token()
def get_member_recent_transactions(request):
    url = f"{os.getenv('api_url')}/members/recent_transactions"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    response = requests.get(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        member_recent_transactions = response.json()
        return member_recent_transactions

    return None


def get_wallet_balance(request):
    url = f"{os.getenv('api_url')}/members/wallet_balance"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == HTTPStatus.OK:
        wallet_balance = response.json()["wallet_balance"]
        return wallet_balance
    else:
        return None


def get_wallet_id(user_id):
    url = f"{os.getenv('api_url')}/members/wallet_number/{user_id}"
    response = requests.get(url)

    if response.status_code == HTTPStatus.OK:
        wallet_id = response.json()["wallet_number"]
        return wallet_id

    return None


def get_wallet_info(request, member_id):
    url = f"{os.getenv('api_url')}/members/wallet_info/{member_id}"
    response = requests.get(url)
    if response.status_code == HTTPStatus.OK:
        wallet_bal = response.json()["wallet_balance"]
        wallet_number = response.json()["wallet_number"]
        return wallet_bal, wallet_number
    return None, None


def get_member_wallet_number(member_id):
    url = f"{os.getenv('api_url')}/members/wallet_number/{member_id}"
    response = requests.get(url)
    if response.status_code == HTTPStatus.OK:
        wallet_number = response.json()["wallet_number"]
        return wallet_number


def get_member_expected_contribution(user_id, activity_id):
    url = (
        f"{os.getenv('api_url')}/members/expected_contribution/{user_id}/{activity_id}"
    )
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        return resp.json()["expected_contribution"]
    return None


def get_user_id(email):
    url = f"{os.getenv('api_url')}/users/id/{email}"
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        user = resp.json()
        user_id = user["User_id"]
        return user_id
    return None


def get_user_full_name(user_id):
    url = f"{os.getenv('api_url')}/users/names/{user_id}"
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        user = resp.json()
        full_name = f"{user['first_name']} {user['last_name']}"
        return full_name
    return None


def get_user_email(user_id):
    url = f"{os.getenv('api_url')}/users/email/{user_id}"
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        user = resp.json()
        email = user["email"]
        return email
    return None


def get_user_phone_number(id):
    url = f"{os.getenv('api_url')}/users/phone_number/{id}"
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        user = resp.json()
        phone_number = user["phone_number"]
        return phone_number
    return None


def get_user_full_profile(id):
    url = f"{os.getenv('api_url')}/users/full_profile/{id}"
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        user = resp.json()
        return user
    return None


def get_user_profile_image(id):
    url = f"{os.getenv('api_url')}/users/full_profile/{id}"
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        user = resp.json()
        return user.get("profile_image")
    return None


def get_member_contribution_so_far(user_id, activity_id):
    resp = requests.get(
        f"{os.getenv('api_url')}/members/contribution_so_far/{user_id}/{activity_id}"
    )
    if resp.status_code == HTTPStatus.OK:
        return resp.json()["total_contribution"]

    return 0


def member_already_in_chama(chama_id, member_id):
    data = {"chama_id": chama_id, "member_id": member_id}
    resp = requests.get(f"{os.getenv('api_url')}/members/member_in_chama", json=data)
    if resp.status_code == HTTPStatus.OK:
        print("====member_in_chama: ", resp.json())
        return resp.json()["is_member"]

    return None


def get_transaction_fee(amount):
    print("====get_transaction_fee: ", amount)
    url = f"{os.getenv('api_url')}/members/chamazetu_to_mpesa_fee/{amount}"
    response = requests.get(url)
    if response.status_code == HTTPStatus.OK:
        print("====get_transaction_fee: ", response.json())
        return response.json()["transaction_fee"]
    return None
