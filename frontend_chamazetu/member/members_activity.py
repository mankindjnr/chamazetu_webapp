import requests, jwt, json, threading
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from datetime import datetime, date, timedelta
from django.contrib import messages
from collections import defaultdict

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.chamas import (
    get_chama_id,
    get_chama_creation_date,
    get_chama_contribution_day,
    get_previous_contribution_date,
    get_chama_contribution_interval,
    get_members_daily_contribution_in_given_month,
    fourth_contribution_date_from_the_upcoming,
)
from chama.thread_urls import fetch_data
from .date_day_time import get_sunday_date, extract_date_time
from .members import get_member_expected_contribution, get_user_full_name

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


def members_tracker(request, chama_name):
    chama_id = get_chama_id(chama_name)
    interval = get_chama_contribution_interval(chama_id)["contribution_interval"]
    fourth_prev_date = fourth_contribution_date_from_the_upcoming(chama_id, interval)
    upcoming_date = datetime.strptime(
        get_chama_contribution_day(chama_id)["contribution_date"], "%d-%B-%Y"
    ).strftime("%d-%m-%Y")
    monthly_tracker_data = organise_monthly_tracker(
        get_members_daily_contribution_in_given_month(chama_id, fourth_prev_date),
        fourth_prev_date,
        upcoming_date,
        chama_id,
    )
    return render(
        request,
        "member/members_tracker.html",
        {
            "chama_name": chama_name,
            "monthly_tracker_data": monthly_tracker_data["transactions_organised"],
            "dates": monthly_tracker_data["dates"],
        },
    )


def organise_monthly_tracker(transactions, back_date, upcoming_date, chama_id):
    creation_date = get_chama_creation_date(chama_id)
    if creation_date:
        if datetime.strptime(back_date, "%d-%m-%Y") < datetime.strptime(
            creation_date, "%d-%m-%Y"
        ):
            back_date = creation_date

    transactions = transactions["members_contribution"]
    dates_from_back_to_upcoming = get_dates_from_back_to_upcoming(
        back_date, upcoming_date
    )

    transactions_with_names = {}
    transactions_organised = {}
    # we will use defaultdict to store the data
    for member_id, member_transactions in transactions.items():
        member_name = get_user_full_name("member", member_id)
        member_tracker = defaultdict(int)
        for date in dates_from_back_to_upcoming:
            # date = '28-03-2024'
            if date in member_transactions:
                member_tracker[date] = member_transactions[date]
            else:
                member_tracker[date] = 0
        transactions_with_names[member_name] = member_tracker

    # Convert defaultdict to regular dictionary for each contributor
    for member, contributions_dict in transactions_with_names.items():
        transactions_organised[member] = dict(contributions_dict)

    return {
        "transactions_organised": transactions_organised,
        "dates": dates_from_back_to_upcoming,
    }


def get_dates_from_back_to_upcoming(back_date, upcoming_date):
    back_date = datetime.strptime(back_date, "%d-%m-%Y") + timedelta(days=1)
    upcoming_date = datetime.strptime(upcoming_date, "%d-%m-%Y")
    # get the dates between backdate and upcoming date
    dates = []
    while back_date <= upcoming_date:
        dates.append(back_date)
        back_date = back_date + timedelta(days=1)

    new_dates = []
    for date in dates:
        new_dates.append(date.strftime("%d-%m-%Y"))

    return new_dates
