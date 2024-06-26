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
)
from .transaction_code import generate_transaction_code

load_dotenv()


def b2ctrial(request):
    print("trial b2c")
    resp = requests.post(f"{os.getenv('api_url')}/businesstocustomer/b2c")
    print("=============business to customer trial=============")
    print(resp.json())

    return HttpResponse("b2c trial")


# ==========================================================
@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def direct_deposit_to_chama(request):
    if request.method == "POST":
        amount = int(request.POST.get("amount"))
        chama_id = get_chama_id(request.POST.get("chamaname"))
        member_id = get_user_id("member", request.COOKIES.get("current_member"))
        phone_number = (
            request.POST.get("phonenumber")
            if len(request.POST.get("phonenumber")) == 9
            and request.POST.get("phonenumber").isdigit()
            else None
        )
        transaction_type = "deposit"
        transaction_origin = request.POST.get("transaction_origin")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        if (
            amount > 0 and phone_number is not None
        ):  # update to 10 shillings which is minimum for paybills
            # check if amount being deposited is more than expected contribution by subtracting contributed amount from expected amount
            # get the money from mpesa, then run the following code
            # stkpush call with the phone number and amount
            depostinfo = {
                "amount": amount,
                "phone_number": phone_number,
                "recipient": request.POST.get("chamaname"),
                "description": "chamadeposit",
            }

            deposit_resp = requests.post(
                f"{os.getenv('api_url')}/mobile_money/mpesa/stkpush", json=depostinfo
            )
            print("-----direct froom mpesa----")
            print(deposit_resp.json())
            # if the stk push was successfully sent
            if (
                deposit_resp.status_code == 201
                and "CheckoutRequestID" in deposit_resp.json()
            ):
                # all this function will depend on the result of the backend tasks -will listen to it and execute
                checkoutrequestid = deposit_resp.json()["CheckoutRequestID"]
                stk_push_status.apply_async(
                    args=[
                        checkoutrequestid,
                        member_id,
                        chama_id,
                        amount,
                        phone_number,
                        transaction_origin,
                        headers,
                    ],
                    link=after_succesful_chama_deposit.s(),
                )

                messages.success(
                    request,
                    f"mpesa stkpush sent to {phone_number} for Ksh: {amount}.",
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
        amount = int(request.POST.get("amount"))
        chama_id = get_chama_id(request.POST.get("chamaname"))
        chama_name = request.POST.get("chamaname")
        member_id = get_user_id("member", request.COOKIES.get("current_member"))
        transaction_type = "deposit"
        transaction_code = generate_transaction_code(
            transaction_type, "wallet", "chama", member_id
        )

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }

        # check if amount beind deposited is more than the expected contribution by subtracting contributed amount from expected amount
        if amount > 0 and amount <= get_wallet_balance(request):
            # we will call our function here to pay fines and whatever we have left will be updated as amount to deposit, if any else return to chama.
            # remember to exit only after updating the account balance
            print("===============before repaymne==================")

            if member_has_fines_or_missed_contributions(member_id, chama_id):
                print("=======member has fines====")
                # =======checking if member has fines before calling the fine repayment function====
                amount = balance_after_paying_fines_and_missed_contributions(
                    request, amount, member_id, chama_id, transaction_code, chama_name
                )
            # after repaymnet, we will have to a bg task to updae transacto=ion table witha fine transaction
            print("===============after repaymne==================")
            print(amount)

            if amount > 0:
                print("====bal > than 0================")
                expected_difference = difference_btwn_contributed_and_expected(
                    member_id, chama_id
                )
                print("=======expected difference is zero===")
                print(expected_difference)
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
                    print(amount, "::", expected_difference)
                    excess_amount = amount - expected_difference
                    print("=======excess amount===")
                    print(excess_amount)
                    amount_to_deposit = expected_difference
                    print("=======amount to deposit===")
                    print(amount_to_deposit)
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
                    print("=======deposting to delay===")
                    print(amount)
                    update_chama_account_balance.delay(
                        chama_id, amount, transaction_type
                    )
                    update_wallet_balance.delay(
                        headers,
                        amount,
                        chama_id,
                        "moved_to_chama",
                        transaction_code,
                    )
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
        transaction_origin = "direct_deposit"
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
            depostinfo = {
                "amount": amount,
                "phone_number": phonenumber,
                "recipient": "wallet",
                "description": "walletdeposit",
            }

            deposit_resp = requests.post(
                f"{os.getenv('api_url')}/mobile_money/mpesa/stkpush", json=depostinfo
            )
            if (
                deposit_resp.status_code == 201
                and "CheckoutRequestID" in deposit_resp.json()
            ):
                checkoutrequestid = deposit_resp.json()["CheckoutRequestID"]

                stk_push_status.apply_async(
                    args=[
                        checkoutrequestid,
                        member_id,
                        "wallet",
                        amount,
                        phonenumber,
                        transaction_origin,
                        headers,
                    ],
                    link=wallet_deposit.s(),
                )

                messages.success(request, "mpesa request sent")
            else:
                messages.error(request, "Failed to send stkpush, please try again.")

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
    print("=======expected amount===")
    print(amount_expected)
    # get the amount contributed so far
    amount_contributed_so_far = get_member_contribution_so_far(chama_id, member_id)
    print("=======contributed so far===")
    print(amount_contributed_so_far)
    expected_difference = amount_expected - amount_contributed_so_far
    print("=======difference===")
    print(expected_difference)
    if expected_difference < 0:
        return 0

    return expected_difference


def deposit_is_greater_than_difference(deposited, member_id, chama_id):
    return int(deposited) > difference_btwn_contributed_and_expected(
        member_id, chama_id
    )


# TODO:
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


# balance after repaying fines and missed contributions
def balance_after_paying_fines_and_missed_contributions(
    request, amount, member_id, chama_id, transaction_code, chama_name
):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    # we first move the money from the wallet to the chama if its a success we continue with the repayment
    url = f"{os.getenv('api_url')}/transactions/record_fine_payment"
    data = {
        "amount": amount,
        "transaction_destination": chama_id,
    }

    wallet_response = requests.post(url, headers=headers, json=data)
    if wallet_response.status_code == HTTPStatus.CREATED:
        url = f"{os.getenv('api_url')}/members/repay_fines"
        data = {
            "member_id": member_id,
            "chama_id": chama_id,
            "amount": amount,
        }

        resp = requests.put(url, json=data)

        # using the received amount and balance_after - update wallet, transaction and accout - bg task

        if resp.status_code == HTTPStatus.OK:
            print("======repaying done========")
            paid_fine = amount - resp.json().get("balance_after_fines")
            print(paid_fine)
            update_chama_account_balance.delay(chama_id, paid_fine, "deposit")
            update_wallet_balance.delay(
                headers,
                paid_fine,
                chama_id,
                "moved_to_chama",
                transaction_code,
            )
            messages.success(
                request, f"Fines and missed contributions of {paid_fine} deducted."
            )
            return resp.json().get("balance_after_fines")
        else:
            return amount
    else:
        # if the wallet deposit fails, we return the amount to the user to try and deposit again by killing the transaction
        messages.error(request, "Failed to deposit, please try again later.")
        return HttpResponseRedirect(reverse("member:access_chama", args=(chama_name,)))


# check if a member has fienes or missed contributions
def member_has_fines_or_missed_contributions(member_id, chama_id):
    print("====checking for members fines=====")
    url = f"{os.getenv('api_url')}/members/fines"
    data = {"member_id": member_id, "chama_id": chama_id}
    resp = requests.get(url, json=data)
    if resp.status_code == HTTPStatus.OK:
        has_fines = resp.json().get("has_fines")
        print("=======has====")
        print(has_fines)
        return has_fines
    return False
