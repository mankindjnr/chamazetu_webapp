import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from http import HTTPStatus

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from .members import get_user_id
from chama.chamas import get_chama_id
from .tasks import (
    update_chama_account_balance,
    update_wallet_balance,
    wallet_deposit,
    stk_push_status,
    after_succesful_chama_deposit,
)
from .members import (
    get_wallet_balance,
    get_member_expected_contribution,
    get_member_contribution_so_far,
    get_wallet_info,
)
from .transaction_code import generate_transaction_code

load_dotenv()


# ==========================================================
@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def direct_deposit_to_chama(request):
    if request.method == "POST":
        amount = request.POST.get("amount", "").strip()
        if not amount or not amount.replace(".", "", 1).isdigit():
            messages.error(request, "Invalid amount.")
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )
        amount = int(float(amount))

        if amount < 10:
            messages.error(request, "Invalid amount.")
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

        chama_id = get_chama_id(request.POST.get("chamaname"))
        member_id = get_user_id("member", request.COOKIES.get("current_member"))
        phone_number = (
            request.POST.get("phonenumber")
            if len(request.POST.get("phonenumber")) == 10
            and request.POST.get("phonenumber").isdigit()
            else None
        )
        transaction_type = "deposit"
        transaction_origin = request.POST.get("transaction_origin")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        if phone_number is not None:
            depostinfo = {
                "amount": amount,
                "phone_number": phone_number[1:],
                "recipient": request.POST.get("chamaname").replace(" ", "").upper(),
                "description": "chamadeposit",
            }

            deposit_resp = requests.post(
                f"{os.getenv('api_url')}/request/push", json=depostinfo
            )
            print("-----direct froom mpesa----")
            if deposit_resp.status_code == HTTPStatus.CREATED:
                # if the stk push was successfully sent
                if "CheckoutRequestID" in deposit_resp.json():
                    # all this function will depend on the result of the backend tasks -will listen to it and execute
                    checkoutrequestid = deposit_resp.json()["CheckoutRequestID"]
                    stk_push_status.apply_async(
                        args=[
                            checkoutrequestid,
                            member_id,
                            chama_id,
                            amount,
                            phone_number[1:],
                            transaction_origin,
                            headers,
                        ],
                        link=after_succesful_chama_deposit.s(),
                    )

                    messages.success(
                        request,
                        f"mpesa stkpush sent to 0{phone_number} for Ksh: {amount}.",
                    )
                    return HttpResponseRedirect(
                        reverse(
                            "member:access_chama", args=(request.POST.get("chamaname"),)
                        )
                    )
                else:
                    messages.error(request, "Failed to send stkpush, please try again.")
                    return HttpResponseRedirect(
                        reverse(
                            "member:access_chama", args=(request.POST.get("chamaname"),)
                        )
                    )
            else:
                messages.error(request, "Failed to send stkpush, please try again.")
                return HttpResponseRedirect(
                    reverse(
                        "member:access_chama", args=(request.POST.get("chamaname"),)
                    )
                )
        else:
            if amount <= 0:
                messages.error(
                    request, "amount has to be greater or equal to one shilling."
                )
            if phone_number is None:
                messages.error(request, "Invalid phone number.")

            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

    return redirect(reverse("member:dashboard"))


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def from_wallet_to_chama(request):
    if request.method == "POST":
        amount = request.POST.get("amount", "").strip()
        if not amount or not amount.replace(".", "", 1).isdigit():
            messages.error(request, "Invalid amount.")
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

        amount = int(float(amount))

        if amount <= 0:
            messages.error(request, "Invalid amount.")
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

        chama_id = get_chama_id(request.POST.get("chamaname"))
        chama_name = request.POST.get("chamaname")
        member_id = get_user_id("member", request.COOKIES.get("current_member"))
        wallet_balance, wallet_number = get_wallet_info(request, member_id)
        if wallet_balance is None:
            messages.error(request, "Failed to get wallet balance.")
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )
        if wallet_balance < 1 or wallet_balance < amount:
            messages.error(request, "Insufficient funds.")
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

        expected_contribution = difference_btwn_contributed_and_expected(
            member_id, chama_id
        )
        # make a unified wallet contribution
        url = f"{os.getenv('api_url')}/members/unified_wallet_contribution"
        data = {
            "expected_contribution": expected_contribution,
            "member_id": member_id,
            "chama_id": chama_id,
            "amount": amount,
        }
        resp = requests.post(url, json=data)
        if resp.status_code == HTTPStatus.CREATED:
            messages.success(request, "chama contribution successful.")
        else:
            messages.error(request, "Failed to deposit, please try again later.")

        return HttpResponseRedirect(
            reverse("member:access_chama", args=(request.POST.get("chamaname"),))
        )

    return redirect(reverse("member:dashboard"))


# deposit to wallet
def deposit_to_wallet(request):
    if request.method == "POST":
        amount = request.POST.get("amount", "").strip()
        if not amount or not amount.replace(".", "", 1).isdigit():
            messages.error(request, "Invalid amount.")
            return redirect(reverse("member:dashboard"))

        amount = int(float(amount))
        if amount < 10:
            messages.error(request, "amount should be greater than ksh 10.")
            return redirect(reverse("member:dashboard"))

        phonenumber = request.POST.get("phonenumber", "").strip()
        if not phonenumber or not phonenumber.isdigit() or len(phonenumber) != 10:
            messages.error(request, "Invalid phone number.")
            return redirect(reverse("member:dashboard"))

        member_id = request.POST.get("member_id")
        transaction_origin = "direct_deposit"

        if not phonenumber:
            messages.error(request, "Invalid phone number")
            return redirect(reverse("member:dashboard"))

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        if amount >= 10:
            depostinfo = {
                "amount": amount,
                "phone_number": phonenumber[1:],
                "recipient": "wallet",
                "description": "walletdeposit",
            }

            deposit_resp = requests.post(
                f"{os.getenv('api_url')}/request/push", json=depostinfo
            )
            if deposit_resp.status_code == HTTPStatus.CREATED:
                if "CheckoutRequestID" in deposit_resp.json():
                    checkoutrequestid = deposit_resp.json()["CheckoutRequestID"]

                    stk_push_status.apply_async(
                        args=[
                            checkoutrequestid,
                            member_id,
                            "wallet",
                            amount,
                            phonenumber[1:],
                            transaction_origin,
                            headers,
                        ],
                        link=wallet_deposit.s(),
                    )

                    messages.success(request, "mpesa request sent")
                else:
                    messages.error(
                        request, "Failed to send mpesa request, please try again."
                    )
            else:
                messages.error(
                    request, "Failed to send mpesa request, please try again."
                )

            return redirect(reverse("member:dashboard"))

    return redirect(reverse("member:dashboard"))


# ==========================================================


# check the difference between the amount deposited and the amount expected within a chama contribution interval
def difference_btwn_contributed_and_expected(member_id, chama_id):
    # get the amount expected
    amount_expected = get_member_expected_contribution(member_id, chama_id)
    # get the amount contributed so far
    amount_contributed_so_far = get_member_contribution_so_far(chama_id, member_id)
    expected_difference = amount_expected - amount_contributed_so_far
    if expected_difference < 0:
        return 0

    return expected_difference


# retrieve the fines a member has
def get_member_fines(member_id, chama_id):
    url = f"{os.getenv('api_url')}/members/total_fines"
    data = {"member_id": member_id, "chama_id": chama_id}
    resp = requests.get(url, json=data)
    if resp.status_code == HTTPStatus.OK:
        return resp.json().get("total_fines")
    return 0


def deposit_is_greater_than_difference(deposited, member_id, chama_id):
    return int(deposited) > difference_btwn_contributed_and_expected(
        member_id, chama_id
    )


# TODO: b2c
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
            "member_id": member_id,
            "transaction_destination": "",  # retrieve the wallet number,
            "amount": amount,
            "transaction_type": "withdrawn_from_wallet",
        }


# balance after repaying fines and missed contributions
def balance_after_paying_fines_and_missed_contributions(
    request, amount, member_id, chama_id, transaction_code, chama_name
):

    url = f"{os.getenv('api_url')}/members/repay_fines"
    expected_contribution = difference_btwn_contributed_and_expected(
        member_id, chama_id
    )
    data = {
        "expected_contribution": expected_contribution,
        "member_id": member_id,
        "chama_id": chama_id,
        "amount": amount,
    }

    resp = requests.put(url, json=data)

    # using the received amount and balance_after - update wallet, transaction and accout - bg task
    if resp.status_code == HTTPStatus.OK:
        balance = resp.json().get("balance_after_fines")  # no need to return it
        messages.success(request, f"Fines and missed contributions of deducted.")
        return balance  # return the amount left after paying fines
    else:
        return amount  # not sure if to return the amount if repayment fails or to return the initial amount

    # if the wallet deposit fails, we return the amount to the user to try and deposit again by killing the transaction
    messages.error(request, "Failed to deposit, please try again later.")
    return HttpResponseRedirect(reverse("member:access_chama", args=(chama_name,)))


# check if a member has fienes or missed contributions
def member_has_fines_or_missed_contributions(member_id, chama_id):
    url = f"{os.getenv('api_url')}/members/fines"
    data = {"member_id": member_id, "chama_id": chama_id}
    resp = requests.get(url, json=data)
    if resp.status_code == HTTPStatus.OK:
        has_fines = resp.json().get("has_fines")
        print("=======has====")
        return has_fines
    return False
