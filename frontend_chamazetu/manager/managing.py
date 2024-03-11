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


@tokens_in_cookies("manager")
def dashboard(request):
    access_token = request.COOKIES.get("access_token")
    current_user = request.COOKIES.get("current_user")

    # might have to add a check for admin/ authorization - add it to the token
    # local validation of token
    response = validate_token(request, "manager")
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, "manager")
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    # get the id of the current mananger
    query = "SELECT id FROM managers WHERE email = %s"
    params = [current_user]
    manager_id = (execute_sql(query, params))[0][0]

    # get the chamas connected to id of the current user
    query = "SELECT chama_name FROM chamas WHERE manager_id = %s AND is_active = True"
    params = [manager_id]
    chamas = execute_sql(query, params)

    print("---------chamas---------")
    print(manager_id)
    print(current_user)
    chama = dict(chamas)
    print(len(chama))
    print()
    return render(
        request,
        "manager/dashboard.html",
        {
            "current_user": current_user,
            "chamas": chamas,
        },
    )


@tokens_in_cookies("manager")
def profile(request, role="manager"):
    response = validate_token(request, role)
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, role)
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    page = f"manager/profile.html"
    return render(request, page)
