import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.rawsql import execute_sql

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


@tokens_in_cookies("member")
def view_chama(request, chamaid):
    response = validate_token(request, "member")
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, "member")
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    data = {"chamaid": chamaid}
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }
    resp = requests.get(
        f"http://chamazetu_backend:9400/chamas/chama", json=data, headers=headers
    )
    if resp.status_code == 200:
        chama = resp.json()["Chama"][0]
        print("---------chama details---------")
        print(chama)
        print()

        return render(
            request,
            "chama/blog_chama.html",
            {
                "chama": chama,
            },
        )


def join_chama(request):
    return HttpResponse("Join Chama")
