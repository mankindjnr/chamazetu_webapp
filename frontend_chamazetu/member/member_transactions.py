import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from .members import get_user_id
from chama.chamas import get_chama_id
from .tasks import (
    update_chama_account_balance,
    update_wallet_balance,
    wallet_deposit,
)
from .members import (
    get_wallet_balance,
    get_member_expected_contribution,
    get_member_contribution_so_far,
)

load_dotenv()


# ==========================================================
@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def direct_deposit_to_chama(request):
    if request.method == "POST":
        amount = int(request.POST.get("amount"))
        chama_id = get_chama_id(request.POST.get("chamaname"))
        member_id = get_user_id("member", request.COOKIES.get("current_member"))
        phone_number = request.POST.get("phonenumber")
        transaction_type = "deposit"
        transaction_origin = request.POST.get("transaction_origin")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        if amount > 0:
            # check if amount being deposited is more than expected contribution by subtracting contributed amount from expected amount
            # get the money from mpesa, then run the following code
            # stkpush call with the phone number and amount
            depostinfo = {
                "amount": amount,
                "phone_number": phone_number,
            }

            deposit_resp = requests.post(
                f"{os.getenv('api_url')}/mobile_money/mpesa/stkpush", json=depostinfo
            )
            print("-----direct froom mpesa----")
            print(deposit_resp.json())
            expected_difference = difference_btwn_contributed_and_expected(
                member_id, chama_id
            )
            if expected_difference == 0:
                update_wallet_balance.delay(
                    headers, amount, chama_id, "moved_to_wallet"
                )
                messages.error(
                    request,
                    f"Excess amount of Ksh: {amount} deposited to wallet. You have already contributed the expected amount for this contribution interval.",
                )
                return HttpResponseRedirect(
                    reverse(
                        "member:access_chama", args=(request.POST.get("chamaname"),)
                    )
                )

            if deposit_is_greater_than_difference(amount, member_id, chama_id):
                excess_amount = amount - expected_difference
                amount_to_deposit = expected_difference
                update_wallet_balance.delay(
                    headers, excess_amount, chama_id, "moved_to_wallet"
                )
                messages.success(
                    request,
                    f"Excess amount of Ksh: {excess_amount} deposited to wallet.",
                )

                amount = amount_to_deposit

            # deposit the amount to chama
            url = f"{os.getenv('api_url')}/transactions/direct_deposit"
            data = {
                "amount": amount,
                "chama_id": chama_id,
                "phone_number": f"254{phone_number}",
                "transaction_origin": transaction_origin,
            }

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 201:
                # call the background task function to update the chama account balance
                update_chama_account_balance.delay(chama_id, amount, transaction_type)
                messages.success(
                    request,
                    f"Deposit of Khs: {amount} to {request.POST.get('chamaname')} successful",
                )
                return HttpResponseRedirect(
                    reverse(
                        "member:access_chama", args=(request.POST.get("chamaname"),)
                    )
                )
            else:
                messages.error(request, "Failed to deposit, please try again.")
                return HttpResponseRedirect(
                    reverse(
                        "member:access_chama", args=(request.POST.get("chamaname"),)
                    )
                )
        else:
            messages.error(
                request, "amount has to be greater or equal to one shilling."
            )
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

    return redirect(reverse("member:dashboard"))


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def from_wallet_to_chama(request):
    if request.method == "POST":
        amount = int(request.POST.get("amount"))
        chama_id = get_chama_id(request.POST.get("chamaname"))
        member_id = get_user_id("member", request.COOKIES.get("current_member"))
        transaction_type = "deposit"
        transaction_origin = request.POST.get("transaction_origin")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        # check if amount beind deposited is more than the expected contribution by subtracting contributed amount from expected amount
        if amount > 0 and amount <= get_wallet_balance(request):
            expected_difference = difference_btwn_contributed_and_expected(
                member_id, chama_id
            )
            if expected_difference == 0:
                messages.error(
                    request,
                    "You have already contributed the expected amount for this contribution interval.",
                )
                return HttpResponseRedirect(
                    reverse(
                        "member:access_chama", args=(request.POST.get("chamaname"),)
                    )
                )

            if deposit_is_greater_than_difference(amount, member_id, chama_id):
                excess_amount = amount - expected_difference
                amount_to_deposit = expected_difference
                amount = amount_to_deposit

            # move from wallet to chama
            url = f"{os.getenv('api_url')}/transactions/deposit_from_wallet"
            data = {
                "amount": amount,
                "transaction_destination": chama_id,
            }

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 201:
                # call the background task function to update the chama account balance
                update_chama_account_balance.delay(chama_id, amount, transaction_type)
                update_wallet_balance.delay(headers, amount, chama_id, "moved_to_chama")
                messages.success(
                    request,
                    f"Moved Khs: {amount} from wallet to {request.POST.get('chamaname')} successfully",
                )
                return HttpResponseRedirect(
                    reverse(
                        "member:access_chama", args=(request.POST.get("chamaname"),)
                    )
                )
            else:
                messages.error(request, "Failed to deposit, please try again.")
                return HttpResponseRedirect(
                    reverse(
                        "member:access_chama", args=(request.POST.get("chamaname"),)
                    )
                )
        else:
            messages.error(
                request,
                "amount has to be greater or equal to one shilling and less than or equal to wallet balance.",
            )
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

    return redirect(reverse("member:dashboard"))


# deposit to wallet
def deposit_to_wallet(request):
    print("=======deposting to wallet===")
    if request.method == "POST":
        amount = request.POST.get("amount")
        phonenumber = request.POST.get("phonenumber")
        member_id = request.POST.get("member_id")
        chama_name = ""  # helps if we are depositng from insde a chama to redirect back to the chama
        if request.POST.get("chama_name"):
            chama_name = request.POST.get("chama_name")
        if len(phonenumber) != 9:
            messages.error(request, "Invalid phone number")
            return redirect(reverse("member:dashboard"))

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        if int(amount) > 0:
            print("=======deposting to delay===")
            wallet_deposit.delay(headers, amount, member_id)
            # messages.success(request, "Deposit to wallet successful.") - callbakc function will handle this
            if chama_name:
                return redirect(
                    reverse(
                        "member:access_chama", args=[request.POST.get("chama_name")]
                    )
                )
            else:
                return redirect(reverse("member:dashboard"))
    print("=======not a post wallet===")
    return redirect(reverse("member:dashboard"))


# ==========================================================


# check the difference between the amount deposited and the amount expected within a chama contribution interval
def difference_btwn_contributed_and_expected(member_id, chama_id):
    # get the amount expected
    amount_expected = get_member_expected_contribution(member_id, chama_id)
    # get the amount contributed so far
    amount_contributed_so_far = get_member_contribution_so_far(chama_id, member_id)
    expected_difference = amount_expected - amount_contributed_so_far

    return expected_difference


def deposit_is_greater_than_difference(deposited, member_id, chama_id):
    return int(deposited) > difference_btwn_contributed_and_expected(
        member_id, chama_id
    )


def withdraw_from_wallet(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        member_id = request.POST.get("member_id")
        chama_name = ""
        if request.POST.get("chama_name"):
            chama_name = request.POST.get("chama_name")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        url = f"{os.getenv('api_url')}/members/update_wallet_balance"
        data = {
            "transaction_destination": 0,
            "amount": amount,
            "transaction_type": "withdrawn_from_wallet",
        }
