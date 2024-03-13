import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from django.contrib import messages

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
    query = "SELECT chama_name, is_active FROM chamas WHERE manager_id = %s"
    params = [manager_id]
    chamas = execute_sql(query, params)

    print("---------chamas---------")
    print(manager_id)
    print(current_user)
    chamas = dict(chamas)
    print(chamas)
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
def chamas(request):
    if request.POST:
        chama_name = request.POST.get("chama_name")
        description = request.POST.get("description")
        members_allowed = request.POST.get("members")
        registration_fee = request.POST.get("registration")
        share_price = request.POST.get("share_price")
        contribution_frequency = request.POST.get("frequency")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")

        # check if start_date is less than end_date and if start date is today and change the is_active to True

        chama_manager = request.COOKIES.get("current_user")

        query = "SELECT id FROM managers WHERE email = %s"
        params = [chama_manager]
        manager_id = (execute_sql(query, params))[0][0]

        query = "INSERT INTO chamas (chama_name, num_of_members_allowed, description, registration_fee, contribution_amount, contribution_interval, start_cycle, end_cycle, manager_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = [
            chama_name,
            description,
            members_allowed,
            registration_fee,
            share_price,
            contribution_frequency,
            start_date,
            end_date,
            manager_id,
        ]
        execute_sql(query, params)

        data = {
            "chama_name": chama_name,
            "description": description,
            "num_of_members_allowed": members_allowed,
            "registration_fee": registration_fee,
            "contribution_amount": share_price,
            "contribution_interval": contribution_frequency,
            "start_cycle": start_date,
            "end_cycle": end_date,
            "manager_id": manager_id,
        }

        headers = {"Content-type": "application/json"}
        response = requests.post(
            "http://chamazetu_backend:9400/chamas",
            data=json.dumps(data),
            headers=headers,
        )
        print("---------chama creation response---------")
        print(response.status_code)
        print()
        if response.status_code == 201:
            messages.success(request, "Chama created successfully.")
            return redirect(reverse("manager:dashboard"))

    return redirect(reverse("manager:dashboard"))


@tokens_in_cookies("manager")
def profile(request, role="manager"):
    response = validate_token(request, role)
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, role)
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    page = f"manager/profile.html"
    return render(request, page)
