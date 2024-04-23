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
from .membermanagement import is_empty_dict
from .date_day_time import get_sunday_date, extract_date_time
from .members import get_member_expected_contribution, get_user_full_name

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
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
            "chama_name": chama_name,
            "monthly_tracker_data": monthly_tracker_data["transactions_organised"],
            "dates": monthly_tracker_data["dates"],
            "chama_days_tracker": chama_days_tracker["chama_days_tracker"],
            "contribution_dates": chama_days_tracker["latest_four_dates"],
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


def chama_days_contribution_tracker(request, chama_id, interval):
    # retrieve the last four contribution dates from the upcoming date
    latest_four_dates = get_chamas_last_four_contribution_days(chama_id)
    print("==latest four dates==")
    print(latest_four_dates)

    urls = []

    for date in latest_four_dates:
        data = {}  # due to python's handling of mutable objects
        data["upto_date"] = datetime.strptime(date, "%d-%m-%Y")
        if interval == "daily":
            data["from_date"] = get_the_from_dates(data["upto_date"])
        elif interval == "weekly":
            data["from_date"] = get_the_from_dates("weekly", data["upto_date"])
        elif interval == "monthly":
            data["from_date"] = get_the_from_dates("monthly", data["upto_date"])

        data["upto_date"] = data["upto_date"].strftime("%d-%m-%Y")
        data["from_date"] = data["from_date"].strftime("%d-%m-%Y")

        urls.append(
            (
                f"{config('api_url')}/members_tracker/chama_days_contribution_tracker/{chama_id}",
                data,
            )
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }

    responses = chama_contribution_days_threads(urls, headers)
    organised_chama_days_tracker = chama_days_contribution_tracker_organised(
        responses, latest_four_dates, interval
    )

    return {
        "chama_days_tracker": organised_chama_days_tracker,
        "latest_four_dates": latest_four_dates,
    }


# The function below is used to fetch data from the API using threads
"""
since the fetch_queued_data function is being executed asynchronously in different threads
we need to use a queue to store the results of the threads, this way, we will wait for all
threads to finish before we start processing the results.
This should ensure that all threads have finished executing and all results have been stored
in the queue before they are processed.
"""


def chama_contribution_days_threads(urls, headers):
    queue = Queue()
    threads = []

    for url, payload in urls:
        if payload:
            thread = threading.Thread(
                target=fetch_queued_data, args=(url, queue, payload, headers)
            )
        elif is_empty_dict(payload):
            thread = threading.Thread(
                target=fetch_queued_data, args=(url, queue, {}, headers)
            )
        else:
            thread = threading.Thread(target=fetch_queued_data, args=(url, queue))

        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    chama_days_activity = []

    while not queue.empty():
        result = queue.get()
        if result[url]["status"] == 200:
            activity = result[url]["data"]
            if activity["chama_contribution"]:
                chama_days_activity.append(activity["chama_contribution"])

    return chama_days_activity


# arrange the  contributions according to their contribution dates
def chama_days_contribution_tracker_organised(responses, dates, interval):
    """
    responses = [{'2': {'18-04-2024': 230}, '1': {'22-04-2024': 230}, '3': {'23-04-2024': 230}}]
    """
    """
    periodical_dates = [{'from_date': '17-04-2024', 'upto_date': '24-04-2024'}, {'from_date': '10-04-2024', 'upto_date': '17-04-2024'}, {'from_date': '03-04-2024', 'upto_date': '10-04-2024'}]
    """
    periodical_dates = []
    for date in dates:
        periodical_dates.append(
            {
                "from_date": get_the_from_dates(
                    interval, datetime.strptime(date, "%d-%m-%Y")
                ).strftime("%d-%m-%Y"),
                "upto_date": date,
            }
        )
    print("-preiodical dates------")
    print(periodical_dates)
    # we are goin to categorize the contributions according to their dates,
    # the contribution will be organized in that its date is > from_date and <= upto_date

    contributions = {}
    for date in periodical_dates:
        contributions[date["upto_date"]] = {}
        for response in responses:
            for member_id, member_contribution in response.items():
                if (
                    date["from_date"]
                    < list(member_contribution.keys())[0]
                    <= date["upto_date"]
                ):
                    contributions[date["upto_date"]][
                        get_user_full_name("member", member_id)
                    ] = member_contribution

    print("==the contributions==")
    print(contributions)
    return contributions


# a function that gets the from_date
def get_the_from_dates(interval, upto_date):
    if interval == "daily":
        from_date = upto_date - timedelta(days=1)
    elif interval == "weekly":
        from_date = upto_date - timedelta(days=7)
    elif interval == "monthly":
        the_contribution_day = upto_date.day
        prev_month = upto_date.month - 1 if upto_date.month > 1 else 12
        prev_year = upto_date.year if prev_month != 12 else upto_date.year - 1
        if calendar.isleap(prev_year) and prev_month == 2:
            from_date = upto_date.replace(
                day=min(int(the_contribution_day), 29),
                month=prev_month,
                year=prev_year,
            )
        else:
            from_date = upto_date.replace(
                day=int(the_contribution_day), month=prev_month, year=prev_year
            )
    return from_date
