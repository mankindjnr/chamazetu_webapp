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
from .membermanagement import get_user_id
from chama.chamas import get_chama_id
from .tasks import update_chama_account_balance


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def deposit_to_chama(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        chama_id = get_chama_id(request.POST.get("chamaname"))
        phone_number = request.POST.get("phonenumber")
        transaction_type = "deposit"

        url = f"{config('api_url')}/transactions/deposit"
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }
        data = {
            "amount": amount,
            "chama_id": chama_id,
            "phone_number": f"254{phone_number}",
        }
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:
            # call the background task function to update the chama account balance
            update_chama_account_balance.delay(chama_id, amount, transaction_type)
            messages.success(
                request, f"Deposit to {request.POST.get('chamaname')} successful"
            )
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )
        else:
            messages.error(request, "Failed to deposit, please try again.")
            return HttpResponseRedirect(
                reverse("member:access_chama", args=(request.POST.get("chamaname"),))
            )

    return redirect(reverse("member:dashboard"))
