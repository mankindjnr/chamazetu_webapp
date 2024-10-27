import requests, jwt, json, os, httpx, time
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from http import HTTPStatus

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from .members import get_user_id
from .tasks import (
    mpesa_request,
)
from .members import (
    get_wallet_balance,
    get_member_expected_contribution,
    get_member_contribution_so_far,
    get_wallet_info,
    get_wallet_id,
    get_transaction_fee,
)
from .activities import get_activity_info
from .transaction_code import generate_transaction_code

load_dotenv()


# ==========================================================
# at this moment we will only check if there are token in the cookies
# but we won't validate them to see if they are expired or not
# this is avoid intrerrupting the user's flow, but we will generate a new headers to send to the api
@async_tokens_in_cookies()
async def from_wallet_to_activity(
    request, chama_name, chama_id, activity_type, activity_id
):
    if request.method != "POST":
        return redirect(reverse("member:dashboard"))

    current_user = request.COOKIES.get("current_user")
    print("====current_user====: ", current_user)
    user_id = get_user_id(current_user)
    amount = request.POST.get("amount", "").strip()

    # validate amount
    if not is_valid_amount(amount):
        return handle_error(
            request, "invalid amount", chama_name, chama_id, activity_type, activity_id
        )

    amount = int(float(amount))

    # fetch wallet info
    wallet_balance = get_wallet_balance(request)
    if wallet_balance is None:
        return handle_error(
            request,
            "failed to fetch wallet info",
            chama_name,
            chama_id,
            activity_type,
            activity_id,
        )

    if wallet_balance < amount or amount <= 0:
        return handle_error(
            request,
            "insufficient funds",
            chama_name,
            chama_id,
            activity_type,
            activity_id,
        )

    # get expected contribution
    expected_contribution = difference_btwn_contributed_and_expected(
        user_id, activity_id
    )

    if expected_contribution == 0:
        return handle_error(
            request,
            "You have already contributed the expected amount",
            chama_name,
            chama_id,
            activity_type,
            activity_id,
        )

    # make a unified wallet contribution
    # generate a transaction header
    transaction_header = await get_transaction_header(request, current_user)

    url = None
    if activity_type == "merry-go-round":
        url = f"{os.getenv('api_url')}/members/contribute/merry-go-round/{activity_id}"
    else:
        url = f"{os.getenv('api_url')}/members/contribute/generic/{activity_id}"

    data = {
        "expected_contribution": expected_contribution,
        "amount": amount,
    }

    if transaction_header:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=transaction_header)
        if resp.status_code == HTTPStatus.CREATED:
            messages.success(request, "Activity contribution successful")
        else:
            messages.error(request, f"{resp.json()['detail']}")
    return HttpResponseRedirect(
        reverse(
            "member:activities", args=[chama_name, chama_id, activity_type, activity_id]
        )
    )


def is_valid_amount(amount):
    return amount and amount.replace(".", "", 1).isdigit() and float(amount) > 0


def handle_error(request, message, chama_name, chama_id, activity_type, activity_id):
    messages.error(request, message)
    return HttpResponseRedirect(
        reverse(
            "member:activities", args=[chama_name, chama_id, activity_type, activity_id]
        )
    )


async def get_transaction_header(request, current_user):
    url = f"{os.getenv('api_url')}/auth/refresh"
    data = {
        "username": current_user,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data)
    if resp.status_code == HTTPStatus.CREATED:
        return {
            "Content-type": "application/json",
            "Authorization": f"Bearer Bearer {resp.json()['new_access_token']}",
        }

    return None


# check the difference between the amount deposited and the amount expected within a chama contribution interval
def difference_btwn_contributed_and_expected(user_id, activity_id):
    amount_expected = get_member_expected_contribution(user_id, activity_id)
    print("====expected: ", amount_expected)
    amount_contributed_so_far = get_member_contribution_so_far(user_id, activity_id)
    print("====contributed: ", amount_contributed_so_far)
    remaining_balance = amount_expected - amount_contributed_so_far
    print("====remaining: ", remaining_balance)
    if remaining_balance < 0:
        return 0

    return remaining_balance


# this function determines where a wallet transaction goes, either deposit or withdrawal to mpesa
# Wrap the request calls with try-except to prevent read timeout errors
@async_tokens_in_cookies()
async def wallet_transactions(request):
    if request.method == "POST":
        transaction_type = request.POST.get("transaction_type", "").strip()
        amount = request.POST.get("amount", "").strip()
        phone_number, wallet_id = "", ""
        if transaction_type != "transfer":
            phone_number = request.POST.get("phonenumber", "").strip()
        else:
            wallet_id = request.POST.get("walletnumber", "").strip()

        # validate amount
        if not is_valid_amount(amount) or int(float(amount)) < 10:
            messages.error(request, "Invalid amount.")
            return redirect(reverse("member:dashboard"))

        amount = int(float(amount))

        # validate phone number
        if transaction_type != "transfer":
            if (
                not phone_number
                or not phone_number.isdigit()
                or len(phone_number) != 10
            ):
                messages.error(request, "Invalid phone number.")
                return redirect(reverse("member:dashboard"))
        else:
            if (
                not wallet_id
                or wallet_id.strip().upper() == "NULL"
                or len(wallet_id) < 6
            ):
                messages.error(request, "Invalid wallet number.")
                return redirect(reverse("member:dashboard"))

        # route reqest based on transaction type
        if transaction_type == "deposit":
            return await deposit_to_wallet(request, amount, phone_number)
        elif transaction_type == "withdrawal":
            return await from_wallet_to_mpesa(request, amount, phone_number)
        elif transaction_type == "transfer":
            return await transfer_to_another_member(request, amount, wallet_id)

    return redirect(reverse("member:dashboard"))


async def deposit_to_wallet(request, amount, phonenumber):
    user_id = get_user_id(request.COOKIES.get("current_user"))
    wallet_id = get_wallet_id(user_id)

    if amount < 10:
        messages.error(request, "amount should be greater than ksh 10.")
        return redirect(reverse("member:dashboard"))

    if not wallet_id:
        messages.error(request, "Failed to fetch wallet info.")
        return redirect(reverse("member:dashboard"))

    if amount >= 10:
        async with httpx.AsyncClient(timeout=10) as client:
            # record the transaction as pending before sending the request to mpesa
            try:
                pending_transaction = await client.post(
                    f"{os.getenv('api_url')}/transactions/unprocessed_deposit",
                    json={
                        "amount": amount,
                        "transaction_type": "unprocessed wallet deposit",
                        "transaction_origin": f"254{phonenumber[1:]}",
                        "transaction_destination": wallet_id,
                        "user_id": user_id,
                    },
                )

                if pending_transaction.status_code == HTTPStatus.CREATED:
                    transaction_code = pending_transaction.json()["transaction_code"]

                    # step 2: send stk push request to mpesa
                    stk_request_resp = await client.post(
                        f"{os.getenv('api_url')}/request/push",
                        json={
                            "amount": amount,
                            "phone_number": f"254{phonenumber[1:]}",
                            "transaction_destination": wallet_id,
                            "transaction_code": transaction_code,
                            "description": "loading wallet",
                        },
                    )

                    if stk_request_resp.status_code == HTTPStatus.CREATED:
                        messages.success(request, "Mpesa Request sent successfully.")
                    else:
                        messages.error(
                            request, "Failed to send mpesa request, please try again."
                        )

                else:
                    messages.error(
                        request, "Failed to record transaction, please try again."
                    )

            except httpx.TimeoutException:
                messages.error(request, "Failed to send mpesa request")
            except httpx.RequestError as exc:
                messages.error(request, "Failed to send mpesa request")

    return redirect(reverse("member:dashboard"))


# ==========================================================
# ==========================================================


@async_tokens_in_cookies()
async def from_wallet_to_select_activity(request, chama_id, chama_name):
    if request.method != "POST":
        return redirect(reverse("member:dashboard"))
    if request.POST.get("activity_title") is None:
        messages.error(request, "No activity selected")
        return redirect(reverse("member:access_chama", args=[chama_name, chama_id]))

    current_user = request.COOKIES.get("current_user")
    user_id = get_user_id(current_user)
    amount = request.POST.get("amount", "").strip()
    activity_id, activity_type = get_activity_info(request.POST.get("activity_title"))

    # validate amount
    if not is_valid_amount(amount):
        return handle_error(
            request, "invalid amount", chama_name, chama_id, activity_type, activity_id
        )

    amount = int(float(amount))

    # fetch wallet info
    wallet_balance = get_wallet_balance(request)
    if wallet_balance is None:
        return handle_error(
            request,
            "failed to fetch wallet info",
            chama_name,
            chama_id,
            activity_type,
            activity_id,
        )

    if wallet_balance < amount or amount <= 0:
        return handle_error(
            request,
            "insufficient funds",
            chama_name,
            chama_id,
            activity_type,
            activity_id,
        )

    # get expected contribution
    expected_contribution = difference_btwn_contributed_and_expected(
        user_id, activity_id
    )

    if expected_contribution == 0:
        messages.error(request, "You have already contributed the expected amount")
        return HttpResponseRedirect(
            reverse("member:access_chama", args=[chama_name, chama_id])
        )

    # make a unified wallet contribution
    # generate a transaction header
    transaction_header = await get_transaction_header(request, current_user)

    url = None
    if activity_type == "merry-go-round":
        url = f"{os.getenv('api_url')}/members/contribute/merry-go-round/{activity_id}"
    elif activity_type == "table-banking":
        url = f"{os.getenv('api_url')}/members/contribute/table-banking/{activity_id}"
    else:
        url = f"{os.getenv('api_url')}/members/contribute/generic/{activity_id}"

    data = {
        "expected_contribution": expected_contribution,
        "amount": amount,
    }

    if transaction_header:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, headers=transaction_header)
        if resp.status_code == HTTPStatus.CREATED:
            messages.success(request, "Activity contribution successful")
        else:
            messages.error(request, f"{resp.json()['detail']}")

    return HttpResponseRedirect(
        reverse("member:access_chama", args=[chama_name, chama_id])
    )


# fixing a wallet deposit from mpesa
@async_tokens_in_cookies()
async def fix_mpesa_to_wallet_deposit(request):
    if request.method == "POST":
        amount = request.POST.get("fix_amount", "").strip()
        if not is_valid_amount(amount):
            messages.error(request, "Invalid amount.")
            return redirect(reverse("member:dashboard"))

        phone_number = request.POST.get("phone_number", "").strip()
        if not phone_number or not phone_number.isdigit() or len(phone_number) != 10:
            messages.error(request, "Invalid phone number.")
            return redirect(reverse("member:dashboard"))

        receipt_number = (request.POST.get("receipt_number", "").strip()).upper()
        if not receipt_number:
            messages.error(request, "Invalid receipt number.")
            return redirect(reverse("member:dashboard"))

        print("====receipt_number: ", receipt_number)

        transaction_headers = await get_transaction_header(
            request, request.COOKIES.get("current_user")
        )

        # check if the transaction exists
        transaction = requests.get(
            f"{os.getenv('api_url')}/transactions/unprocessed_deposit/254{phone_number[1:]}/{amount}/{receipt_number}",
            headers=transaction_headers,
        )
        if transaction.status_code == HTTPStatus.OK:
            transaction_data = transaction.json()
            if transaction_data["unprocessed_transaction_exists"] is True and transaction_data["transaction_code"]:
                # Fix the transaction
                transaction_code = transaction_data["transaction_code"]
                update_transaction = requests.put(
                    f"{os.getenv('api_url')}/callback/fix_unprocessed_deposit/{transaction_code}/{receipt_number}",
                    headers=transaction_headers,
                )
                if update_transaction.status_code == HTTPStatus.OK:
                    messages.success(request, "Your transaction is being processed, refresh the page after 5 minutes.")
                else:
                    messages.error(
                        request, "Failed to update transaction. confirm receipt number."
                    )
            else:
                messages.error(request, "Transaction not found, please try again later.")
        else:
            messages.error(
                request, f"{transaction.json()['detail']}. Confirm the receipt number and try again."
            )

    return redirect(reverse("member:dashboard"))


# ==========================================================
# b2c transactions
async def from_wallet_to_mpesa(request, amount, phone_number):
    current_user = request.COOKIES.get("current_user")
    user_id = get_user_id(current_user)

    # fetch wallet info
    wallet_balance = get_wallet_balance(request)
    if wallet_balance is None:
        messages.error(request, "failed to fetch wallet info")
        return redirect(reverse("member:dashboard"))

    # get the cost of the transaction
    transaction_fee = get_transaction_fee(amount)
    if transaction_fee is None:
        messages.error(request, "Withdrawal failed. Please try again later.")
        return redirect(reverse("member:dashboard"))

    amount_to_withdraw = amount + transaction_fee

    if wallet_balance < amount_to_withdraw or amount <= 0:
        messages.error(
            request, f"Could not complete the transaction. Insufficient funds."
        )
        return redirect(reverse("member:dashboard"))

    # generate a transaction header
    transaction_header = await get_transaction_header(request, current_user)

    # first request to the withdrawal api
    url_unprocessed = (
        f"{os.getenv('api_url')}/transactions/unprocessed_wallet_withdrawal"
    )
    data_unprocessed = {
        "amount": amount,
        "transaction_destination": f"254{phone_number[1:]}",  # remove the 0
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            unprocessed_resp = await client.post(
                url_unprocessed, json=data_unprocessed, headers=transaction_header
            )

            if unprocessed_resp.status_code == HTTPStatus.CREATED:
                transaction_code = unprocessed_resp.json()["transaction_code"]

                # second request to the send b2c api
                url_mpesa = f"{os.getenv('api_url')}/request/send"
                data_mpesa = {
                    "amount": amount,
                    "phone_number": f"254{phone_number[1:]}",
                    "description": "wallet withdrawal",
                    "originator_conversation_id": transaction_code,
                }

                # send the request to mpesa and handle errors
                try:
                    resp = await client.post(url_mpesa, json=data_mpesa)
                    if resp.status_code == HTTPStatus.CREATED:
                        messages.success(
                            request, "Withdrawal request sent successfully"
                        )
                    else:
                        messages.error(request, "Failed to send withdrawal request")
                except httpx.RequestError:
                    messages.error(request, "Failed to send withdrawal request")
            else:
                messages.error(
                    request,
                    "Failed to send withdrawal request. Please try again later.",
                )
    except httpx.RequestError as exc:
        messages.error(request, "Failed to send withdrawal request")
    except httpx.TimeoutException:
        messages.error(request, "Failed to send withdrawal request")

    return redirect(reverse("member:dashboard"))


# ==========================================================
async def transfer_to_another_member(request, amount, wallet_id):
    current_user = request.COOKIES.get("current_user")
    # generate a transaction header
    transaction_header = await get_transaction_header(request, current_user)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            transfer_url = f"{os.getenv('api_url')}/transactions/transfer"
            transfer_data = {
                "amount": amount,
                "destination_wallet": wallet_id.strip().upper(),
            }
            # send the request to mpesa and handle errors
            try:
                resp = await client.post(
                    transfer_url, json=transfer_data, headers=transaction_header
                )
                if resp.status_code == HTTPStatus.CREATED:
                    messages.success(request, "Transfer request sent successfully")
                else:
                    messages.error(request, f"{resp.json()['detail']}")
            except httpx.RequestError:
                messages.error(request, "Failed to send transfer request")
    except httpx.RequestError as exc:
        messages.error(request, "Failed to send transfer request")
    except httpx.TimeoutException:
        messages.error(request, "Failed to send transfer request")

    return redirect(reverse("member:dashboard"))
