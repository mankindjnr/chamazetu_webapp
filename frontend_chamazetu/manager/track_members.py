import calendar, requests, jwt, json, threading
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from datetime import datetime, date, timedelta
from django.contrib import messages
from collections import defaultdict
from queue import Queue

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.chamas import (
    get_chama_id,
    get_chama_creation_date,
    get_chama_contribution_day,
    get_previous_contribution_date,
    get_chama_contribution_interval,
    get_chamas_last_four_contribution_days,
    fourth_contribution_date_from_the_upcoming,
    get_members_daily_contribution_in_given_month,
)
from chama.thread_urls import fetch_data
from chama.queued_thread_urls import fetch_queued_data
from member.members_activity import (
    organise_monthly_tracker,
    get_dates_from_back_to_upcoming,
    chama_days_contribution_tracker,
    chama_days_contribution_tracker_organised,
)

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


@tokens_in_cookies("manager")
@validate_and_refresh_token("manager")
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
    chama_days_tracker = chama_days_contribution_tracker(request, chama_id, interval)
    return render(
        request,
        "member/members_tracker.html",
        {
            "role": "manager",
            "chama_name": chama_name,
            "monthly_tracker_data": monthly_tracker_data["transactions_organised"],
            "dates": monthly_tracker_data["dates"],
            "members_tracker": chama_days_tracker["members_tracker"],
            "contribution_dates": chama_days_tracker["latest_four_dates"],
        },
    )
