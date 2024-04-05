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
def dashboard(request):
    # backend validation of token
    current_user = request.COOKIES.get("current_member")

    # TODO: replace this with a call to the backend
    # get the current users id
    try:
        query = "SELECT id FROM members WHERE email = %s"
        params = [current_user]
        member_id = (execute_sql(query, params))[0][0]
        # use the id to get the chama the user is in from the associate table
        query = "SELECT chama_id FROM members_chamas WHERE member_id = %s"
        params = [member_id]
        chama_ids = execute_sql(query, params)
    except Exception as e:
        print(e)
        chama_ids = None

    chamas_gen = (chama[0] for chama in chama_ids)
    chama_ids = list(chamas_gen)

    data = {"chamaids": chama_ids}

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    resp = requests.get(
        f"{config('api_url')}/chamas/my_chamas", json=data, headers=headers
    )

    if resp.status_code == 200:
        chamas = resp.json()["Chama"]

        return render(
            request,
            "member/dashboard.html",
            {
                "current_user": current_user,
                "chamas": chamas,
            },
        )
    else:
        return render(request, "member/dashboard.html")


def get_user_id(role, email):
    url = f"{config('api_url')}/users/{role}/{email}"
    resp = requests.get(url)
    user = resp.json()
    user_id = user["User_id"]
    return user_id


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def profile(request, role="member"):
    page = f"member/profile.html"
    return render(request, page)
