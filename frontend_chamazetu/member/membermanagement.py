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
def dashboard(request):
    access_token = request.COOKIES.get("access_token")
    print("-------member-sync-check--------")
    print(access_token)

    # backend validation of token
    current_user = request.COOKIES.get("current_user")
    print("---------current_user---------")
    print(current_user)
    response = validate_token(request, "member")
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, "member")
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    # get the current users id
    try:
        query = "SELECT id FROM members WHERE email = %s"
        params = [current_user]
        member_id = (execute_sql(query, params))[0][0]
        # use the id to get the chama the user is in from the associate table
        query = "SELECT chama_id FROM members_chamas WHERE member_id = %s"
        params = [member_id]
        chama_ids = (execute_sql(query, params))[0][0]
    except Exception as e:
        print(e)
        chama_ids = None

    print("---------chama_id---------")
    print(chama_ids)

    return render(
        request,
        "member/dashboard.html",
        {
            "current_user": current_user,
            "chama_ids": chama_ids,
        },
    )


@tokens_in_cookies("member")
def profile(request, role="member"):
    response = validate_token(request, role)
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, role)
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    page = f"member/profile.html"
    return render(request, page)
