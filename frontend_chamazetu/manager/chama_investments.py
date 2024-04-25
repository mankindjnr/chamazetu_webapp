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
from .tasks import update_investment_account
from member.tasks import update_chama_account_balance


from chama.usermanagement import (
    validate_token,
    refresh_token,
)


# invest to an investment
@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
def invest(request):
    if request.method == "POST":
        chama_name = (request.POST.get("chama_name")).strip()
        chama_id = get_chama_id(chama_name)
        investment_amt = request.POST.get("invest_amount")
        investment_type = request.POST.get("investment_type")
        transaction_type = "deposit"

        data = {
            "chama_id": chama_id,
            "amount": investment_amt,
            "transaction_type": transaction_type,
            "investment_type": investment_type,
        }

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        # check if amount invested is more than the account balance before making requests
        if amount_is_within_balance(chama_id, investment_amt, "invest"):
            response = requests.post(
                f"{config('api_url')}/investments/chamas/{investment_type}",
                json=data,
                headers=headers,
            )

            if response.status_code == 201:
                # update both the investment and account balances after successful investment
                update_investment_account.delay(
                    chama_id, investment_amt, investment_type, transaction_type
                )
                # an investment is a withdrawal from the account balance
                update_chama_account_balance.delay(chama_id, investment_amt, "withdraw")
                messages.success(
                    request,
                    f"{investment_type} investment of Ksh: {investment_amt} for {chama_name} was successful",
                )
                return HttpResponseRedirect(
                    reverse("manager:chama", args=(chama_name,))
                )
            else:
                messages.error(
                    request, "The deposit failed, please try again in a few."
                )
                return HttpResponseRedirect(
                    reverse("manager:chama", args=(chama_name,))
                )
        else:
            messages.error(
                request,
                "You cannot invest more than is available in your current account.",
            )
            return redirect(reverse("manager:chama", args=[chama_name]))

    return redirect(reverse("manager:dashboard"))


def withdraw_from_investment(request):
    if request.method == "POST":
        chama_name = request.POST.get("chama_name")
        chama_id = get_chama_id(chama_name)
        withdraw_amount = request.POST.get("withdraw_amount")
        investment_type = request.POST.get("investment_type")
        transaction_type = "withdraw"

        data = {
            "chama_id": chama_id,
            "amount": withdraw_amount,
            "transaction_type": transaction_type,
        }

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        # check if the withdrawal amt is above the investment bal
        if amount_is_within_balance(chama_id, withdraw_amount, "withdraw"):
            response = requests.post(
                f"{config('api_url')}/investments/chamas/{investment_type}",
                json=data,
                headers=headers,
            )

            if response.status_code == 201:
                update_investment_account.delay(
                    chama_id, withdraw_amount, investment_type, transaction_type
                )
                # a withdrawal from the investment is a deposit to the current account
                update_chama_account_balance.delay(chama_id, withdraw_amount, "deposit")
                messages.success(
                    request,
                    f"{transaction_type}al of Ksh: {withdraw_amount} from {chama_name} investment was successful",
                )
                return HttpResponseRedirect(
                    reverse("manager:chama", args=(chama_name,))
                )
            else:
                messages.error(
                    request, "The withdrawal failed, please try again later."
                )
                return HttpResponseRedirect(
                    reverse("manager:chama", args=(chama_name,))
                )
        else:
            messages.error(
                request, "you cannot withdraw more than your current investment balance"
            )
            return redirect(reverse("manager:chama", args=[chama_name]))

    return redirect(reverse("manager:dashboard"))


def amount_is_within_balance(chama_id, amount, type):
    if type == "invest":  # check current acct bal
        investment_resp = requests.get(
            f"{config('api_url')}/chamas/account_balance/{chama_id}"
        )
        if investment_resp.status_code == 200:
            current_bal = investment_resp.json()["account_balance"]
            if current_bal >= int(amount):
                return True
    elif type == "withdraw":  # check invest acc bal
        withdraw_resp = requests.get(
            f"{config('api_url')}/investments/chamas/account_balance/{chama_id}"
        )
        if withdraw_resp.status_code == 200:
            current_invest_bal = withdraw_resp.json()["amount_invested"]
            if current_invest_bal >= int(amount):
                return True
