import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def view_chama(request, chamaid):
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
                "role": "member",
                "chama": chama,
            },
        )


def join_chama(request):
    return HttpResponse("Join Chama")
