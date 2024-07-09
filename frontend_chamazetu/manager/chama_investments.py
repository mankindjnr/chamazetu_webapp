import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.contrib import messages
from datetime import datetime
from http import HTTPStatus

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_data
from chama.chamas import get_chama_id
from member.member_chama import access_chama_async, recent_transactions
from .tasks import update_investment_account, add_chama_withdrawal_request
from member.tasks import update_chama_account_balance


from chama.usermanagement import (
    validate_token,
    refresh_token,
)

load_dotenv()


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

        # check if the investment amount meets the minimum requirement
        if not amount_meets_min_requirement(investment_amt, investment_type, "invest"):
            messages.error(
                request,
                "The investment amount is below the minimum investment amount for this investment",
            )
            return redirect(reverse("manager:chama", args=[chama_name]))

        # check if amount invested is more than the account balance before making requests
        if amount_is_within_balance(chama_id, investment_amt, "invest"):
            response = requests.post(
                f"{os.getenv('api_url')}/investments/chamas/{investment_type}",
                json=data,
                headers=headers,
            )

            if response.status_code == HTTPStatus.CREATED:
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
                print("============invest error=============")
                messages.error(
                    request, "The investment failed, please try again in a few."
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
        }

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        # check if this withdrawal is within the allowed period
        if not withdrawal_is_within_period(chama_id, investment_type):
            messages.error(
                request,
                "You cannot make a withdrawal before the allowed withdrawal period",
            )
            return redirect(reverse("manager:chama", args=[chama_name]))

        # check if the withdrawal amount meets the minimum requirement
        if not amount_meets_min_requirement(
            withdraw_amount, investment_type, transaction_type
        ):
            messages.error(
                request,
                "The withdrawal amount is below the minimum withdrawal amount for this investment",
            )
            return redirect(reverse("manager:chama", args=[chama_name]))

        # check if the withdrawal amt is greater than the investment balance before making requests
        if amount_is_within_balance(chama_id, withdraw_amount, "withdraw"):
            response = requests.post(
                f"{os.getenv('api_url')}/investments/chamas/withdrawal_requests",
                json=data,
                headers=headers,
            )

            if response.status_code == HTTPStatus.CREATED:
                messages.success(
                    request,
                    f"{transaction_type}al request of Ksh: {withdraw_amount} from {chama_name} investment was successful",
                )
                return HttpResponseRedirect(
                    reverse("manager:chama", args=(chama_name,))
                )
            else:
                messages.error(
                    request, "The withdrawal request failed, please try again later."
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


def amount_is_within_balance(chama_id, amount, transaction_type):
    if transaction_type == "invest":  # check current acct bal
        investment_resp = requests.get(
            f"{os.getenv('api_url')}/chamas/account_balance/{chama_id}"
        )
        if investment_resp.status_code == HTTPStatus.OK:
            current_bal = investment_resp.json()["account_balance"]
            if current_bal >= int(amount):
                return True
    elif transaction_type == "withdraw":  # check invest acc bal
        withdraw_resp = requests.get(
            f"{os.getenv('api_url')}/investments/chamas/account_balance/{chama_id}"
        )
        if withdraw_resp.status_code == HTTPStatus.OK:
            current_invest_bal = withdraw_resp.json()["amount_invested"]
            if current_invest_bal >= int(amount):
                return True


# minimum_investmet_amt is also minimum_withdrawal_amt
def amount_meets_min_requirement(amount, investment_type, transaction_type):
    investment_resp = requests.get(
        f"{os.getenv('api_url')}/investments/chamas/minimum_investment/{investment_type.lower()}"
    )
    if investment_resp.status_code == HTTPStatus.OK:
        min_investment_amt = investment_resp.json()["minimum_investment"]
        min_withdrawal_amt = investment_resp.json()["minimum_withdrawal"]
        if transaction_type == "invest":
            print("============invest===========")
            if int(amount) >= min_investment_amt:
                print("============invest true============")
                return True
        elif transaction_type == "withdraw":
            if int(amount) >= min_withdrawal_amt:
                return True
    return False


# check if the withdrawal is within the allowed timeline i.e investment_period == one withdrawal period
def withdrawal_is_within_period(chama_id, investment_type):
    last_withdrawal = requests.get(
        f"{os.getenv('api_url')}/investments/chamas/last_withdrawal_date/{chama_id}"
    )
    if last_withdrawal.status_code == HTTPStatus.OK:
        last_withdrawal_date = (
            last_withdrawal.json()["last_withdrawal_date"]
            if "last_withdrawal_date" in last_withdrawal.json()
            else None
        )
        if (
            last_withdrawal_date is None
        ):  # if none then this chama has never made a withdrawal
            return True
        print("=============dates================")
        last_withdrawal_date = datetime.strptime(
            last_withdrawal_date, "%Y-%m-%dT%H:%M:%S.%f"
        )
        withdrawal_period = (
            datetime.now() - last_withdrawal_date
        )  # number of days since last withdrawal
        print(withdrawal_period.days)
        print(withdrawal_period)
        investment_resp = requests.get(
            f"{os.getenv('api_url')}/investments/chamas/investment_period/{investment_type.lower()}"
        )

        if investment_resp.status_code == HTTPStatus.OK:
            investment_period = investment_resp.json()["investment_period"]
            period_unit = investment_resp.json()["investment_period_unit"]
            if period_unit == "days":
                print("================days=============")
                if withdrawal_period.days >= investment_period:
                    print("============days true============")
                    return True
            elif period_unit == "months":
                print("================months=============")
                if withdrawal_period.days >= investment_period * 30:
                    print("============months true============")
                    return True
            elif period_unit == "weeks":
                print("================weeks=============")
                if withdrawal_period.days >= investment_period * 7:
                    print("============weeks true============")
                    return True

    return False
