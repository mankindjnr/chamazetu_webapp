import requests, jwt, json, calendar
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from datetime import timedelta, datetime

from .rawsql import execute_sql


# we can later have  asection for chamas that are currently not acceting members so
# members can request to join/ be invited to join/ waitlist
def get_all_chamas(request, role=None):
    chamas_resp = requests.get(
        f"{config('api_url')}/chamas/active_accepting_members_chamas"
    )
    chamas = None
    if chamas_resp.status_code == 200:
        chamas = chamas_resp.json()

    return render(
        request,
        "chama/allchamas.html",
        {
            "role": role,
            "chamas": chamas,
        },
    )


# public chama access
def get_chama(request, chamaid):
    data = {"chamaid": chamaid}

    resp = requests.get(f"{config('api_url')}/chamas/public_chama", json=data)
    if resp.status_code == 200:
        chama = resp.json()["Chama"][0]

        for detail in chama:
            print(detail, ":", chama[detail])

        return render(
            request,
            "chama/blog_chama.html",
            {
                "chama": chama,
            },
        )
    # if the chama is not found, return a 404 page or refresh the page
    return HttpResponse("Chama not found")


def get_chama_id(chamaname):
    resp = requests.get(f"{config('api_url')}/chamas/chama_id/{chamaname}")
    if resp.status_code == 200:
        chama = resp.json()
        chama_id = chama["Chama_id"]
        return chama_id


def get_chama_name(chama_id):
    resp = requests.get(f"{config('api_url')}/chamas/chama_name/{chama_id}")
    if resp.status_code == 200:
        chama = resp.json()
        chama_name = chama["Chama_name"]
        return chama_name


def get_chama_contribution_day(chama_id):
    resp = requests.get(f"{config('api_url')}/chamas/contribution_day/{chama_id}")
    if resp.status_code == 200:
        contribution_details = resp.json()
        return contribution_details
    return "to_be_set"


def get_chama_contribution_interval(chama_id):
    resp = requests.get(f"{config('api_url')}/chamas/contribution_interval/{chama_id}")
    if resp.status_code == 200:
        contribution_interval = resp.json()
        return contribution_interval
    return "to_be_set"


def get_previous_contribution_date(chama_id):
    upcoming_contribution_date = get_chama_contribution_day(chama_id)[
        "contribution_date"
    ]
    previous_contribution_date = "to_be_set"
    # if the contribution day has not been set, return a default date
    if upcoming_contribution_date == "to_be_set":  # fetch from the db
        upcoming_contribution_date = get_chama_contribution_day(chama_id)[
            "contribution_date"
        ]
    else:
        interval, day = get_chama_contribution_interval(chama_id).values()
        if interval == "monthly":
            day = int(day)
            # Subtract a month if interval is monthly
            upcoming_contribution_date = datetime.strptime(
                upcoming_contribution_date, "%d-%B-%Y"
            )
            # extract the month and day from upcoming_contribution_date
            upcoming_day = upcoming_contribution_date.day
            upcoming_month = upcoming_contribution_date.month

            # determine the previous month
            previous_month = upcoming_month - 1 if upcoming_month > 1 else 12

            # determine the previous year
            previous_year = upcoming_contribution_date.year
            if previous_month == 12 and upcoming_month == 1:
                previous_year -= 1

            # calculate the previous contribution date using the current stored day and the previous month
            if upcoming_day >= day:
                previous_contribution_date = datetime(
                    previous_year, previous_month, day
                )
            else:
                # if upcoming day is less than the stored day, go to the previous month
                previous_day = day
                # might have to handle leap years
                previous_contribution_date = datetime(
                    previous_year, previous_month, previous_day
                )
        elif interval == "weekly":
            # Subtract a week if interval is weekly
            upcoming_contribution_date = datetime.strptime(
                upcoming_contribution_date, "%d-%B-%Y"
            )
            previous_contribution_date = upcoming_contribution_date - timedelta(days=7)
        elif interval == "daily":
            # Subtract a day if interval is daily
            upcoming_contribution_date = datetime.strptime(
                upcoming_contribution_date, "%d-%B-%Y"
            )
            # get yesterday's date
            previous_contribution_date = upcoming_contribution_date - timedelta(days=1)

    return previous_contribution_date.strftime("%d-%m-%Y")


def get_members_daily_contribution_in_given_month(chama_id, prev_4th_contribution_date):
    url = f"{config('api_url')}/members_tracker/members_daily_monthly_contribution/{chama_id}"
    data = {"contribution_back_date": prev_4th_contribution_date}
    resp = requests.get(url, json=data)
    if resp.status_code == 200:
        return resp.json()


def fourth_contribution_date_from_the_upcoming(chama_id, interval):
    # we will use the upcoming date to determine the fourth previous contribution date, we will use the interval as well
    upcoming_contribution_date = get_chama_contribution_day(chama_id)[
        "contribution_date"
    ]
    # if the contribution day has not been set, return a default date -14 days
    prev_fourth_contribution_date = datetime.now() - timedelta(days=14)
    if interval == "daily":
        # the the previous 4th contribution date will be 4 days before the upcoming contribution date
        prev_fourth_contribution_date = datetime.strptime(
            upcoming_contribution_date, "%d-%B-%Y"
        ) - timedelta(days=4)
    elif interval == "weekly":
        # the the previous 4th contribution date will be 4 weeks before the upcoming contribution date
        prev_fourth_contribution_date = datetime.strptime(
            upcoming_contribution_date, "%d-%B-%Y"
        ) - timedelta(weeks=4)
    elif interval == "monthly":
        # the the previous 4th contribution date will be 4 months before the upcoming contribution date
        prev_fourth_contribution_date = datetime.strptime(
            upcoming_contribution_date, "%d-%B-%Y"
        ) - timedelta(weeks=16)

    return prev_fourth_contribution_date.strftime("%d-%m-%Y")


def get_chama_creation_date(chama_id):
    resp = requests.get(f"{config('api_url')}/chamas/creation_date/{chama_id}")
    if resp.status_code == 200:
        chama = resp.json()
        creation_date = chama["creation_date"]
        return creation_date
    return None


def get_chama_start_date(chama_id):
    resp = requests.get(f"{config('api_url')}/chamas/start_date/{chama_id}")
    if resp.status_code == 200:
        chama = resp.json()
        start_date = chama["start_date"]
        return start_date
    return None


def get_chamas_last_four_contribution_days(chama_id):
    interval_detail = get_chama_contribution_interval(chama_id)
    interval = interval_detail["contribution_interval"]
    contribution_day = interval_detail["contribution_day"]

    ahead_date = datetime.strptime(
        get_chama_contribution_day(chama_id)["contribution_date"], "%d-%B-%Y"
    )
    print("======upcoming date")
    print(ahead_date)
    chama_start_date = datetime.strptime(get_chama_start_date(chama_id), "%d-%m-%Y")
    print("======chama start date")
    print(chama_start_date)

    dates = []
    if interval == "daily":
        print("===daily===")
        while chama_start_date <= ahead_date:
            dates.append(ahead_date)
            ahead_date -= timedelta(days=1)
    elif interval == "weekly":
        print("===weekly===")
        while chama_start_date <= ahead_date:
            print("times")
            dates.append(ahead_date)
            ahead_date -= timedelta(weeks=1)
    elif interval == "monthly":
        print("===monthly===")
        while chama_start_date <= ahead_date:
            dates.append(ahead_date)
            prev_month = ahead_date.month - 1 if ahead_date.month > 1 else 12
            prev_year = ahead_date.year if prev_month != 12 else ahead_date.year - 1
            if calendar.isleap(prev_year) and prev_month == 2:
                ahead_date = ahead_date.replace(
                    day=min(int(contribution_day), 29), month=prev_month, year=prev_year
                )
            else:
                ahead_date = ahead_date.replace(
                    day=int(contribution_day), month=prev_month, year=prev_year
                )

    latest_four_dates = []
    for date in dates:
        latest_four_dates.append(date.strftime("%d-%m-%Y"))
    return latest_four_dates


def get_chama_number_of_members(chama_id):
    resp = requests.get(f"{config('api_url')}/chamas/members_count/{chama_id}")
    if resp.status_code == 200:
        chama = resp.json()
        number_of_members = chama["number_of_members"]
        return number_of_members
    return 0
