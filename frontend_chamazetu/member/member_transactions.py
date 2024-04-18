import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from .members import get_user_id
from chama.chamas import get_chama_id
from .tasks import update_chama_account_balance, update_wallet_balance
from .members import (
    get_wallet_balance,
    get_member_expected_contribution,
    get_member_contribution_so_far,
)


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def deposit_to_chama(request):
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

        # check if the amount deposited so far, and amount expected, if the the deposit is more than the difference, split the amount, excess to wallet the rest to chama
        if deposit_is_greater_than_difference(amount, member_id, chama_id):
            transaction_type = "move_to_wallet"
            # split the amount between the wallet and the chama - excess to wallet and the rest to chama
            excess_to_wallet = amount - difference_btwn_contributed_and_expected(
                member_id, chama_id
            )
            update_wallet_balance.delay(
                headers, excess_to_wallet, chama_id, transaction_type
            )
            messages.success(request, "Excess amount deposited to wallet.")
            amount = amount - excess_to_wallet  # what remains to be deposited to chama

        if transaction_origin == "direct_deposit":
            url = f"{config('api_url')}/transactions/deposit"
            data = {
                "amount": amount,
                "chama_id": chama_id,
                "phone_number": f"254{phone_number}",
                "transaction_origin": transaction_origin,
            }
            # we can run a simple check to see if the amount is a number and the number is a safaricom number
            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 201:
                # call the background task function to update the chama account balance
                update_chama_account_balance.delay(chama_id, amount, transaction_type)
                messages.success(
                    request, f"Deposit to {request.POST.get('chamaname')} successful"
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
        elif transaction_origin == "wallet_deposit":
            if float(amount) <= get_wallet_balance(request):
                url = f"{config('api_url')}/transactions/deposit_from_wallet"
                data = {
                    "amount": amount,
                    "transaction_destination": chama_id,
                }
                response = requests.post(url, headers=headers, json=data)

                if response.status_code == 201:
                    # call the background task function to update the chama account balance
                    update_chama_account_balance.delay(
                        chama_id, amount, transaction_type
                    )
                    messages.success(
                        request,
                        f"Deposit to {request.POST.get('chamaname')} successful",
                    )
                    return redirect(
                        reverse(
                            "member:access_chama", args=(request.POST.get("chamaname"),)
                        )
                    )
                else:
                    messages.error(request, "Failed to deposit, please try again.")
                    return redirect(
                        reverse(
                            "member:access_chama", args=(request.POST.get("chamaname"),)
                        )
                    )
            else:
                messages.error(request, "Insufficient funds in your wallet.")
                return redirect(
                    reverse("member:access_chama", args=[request.POST.get("chamaname")])
                )

    return redirect(reverse("member:dashboard"))


# check the difference between the amount deposited and the amount expected within a chama contribution interval
def difference_btwn_contributed_and_expected(member_id, chama_id):
    # get the amount expected
    amount_expected = get_member_expected_contribution(member_id, chama_id)

    # get the amount contributed so far
    amount_contributed_so_far = get_member_contribution_so_far(chama_id, member_id)

    return amount_expected - amount_contributed_so_far


def deposit_is_greater_than_difference(amount, member_id, chama_id):
    return int(amount) > difference_btwn_contributed_and_expected(member_id, chama_id)


# deposit to wallet
