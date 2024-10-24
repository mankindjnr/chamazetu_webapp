import requests, jwt, json, threading, os, calendar
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.contrib import messages
from datetime import datetime
import asyncio, aiohttp
from zoneinfo import ZoneInfo
from http import HTTPStatus
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from chama.rawsql import execute_sql
from chama.thread_urls import fetch_chama_data, fetch_data
from chama.chamas import get_chama_id, get_chama_number_of_members, get_chama_name
from member.members import get_user_full_profile, get_user_id
from member.membermanagement import is_empty_dict
from member.date_day_time import extract_date_time
from chama.tasks import (
    update_activities_contribution_days,
    set_contribution_date,
    send_email_invites,
)


from chama.usermanagement import (
    validate_token,
    refresh_token,
    check_token_validity,
)

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def dashboard(request):
    current_role = request.COOKIES.get("current_role")
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    dashboard_resp = requests.get(
        f"{os.getenv('api_url')}/managers/dashboard", headers=headers
    )
    print("===========manager dashboard================")
    # print(dashboard_resp.json(), ":", current_role)

    if dashboard_resp.status_code == HTTPStatus.OK:
        dashboard_results = dashboard_resp.json()
        return render(
            request,
            "manager/dashboard.html",
            {
                "current_user": dashboard_results.get("user_email"),
                "current_role": current_role,
                "manager_id": dashboard_results.get("manager_id"),
                "profile_picture": dashboard_results.get("manager_profile_picture"),
                "chamas": dashboard_results.get("chamas"),
                "updates_and_features": dashboard_results.get("updates_and_features"),
            },
        )

    messages.error(request, "An error occurred.")
    return redirect(reverse("signin"))


@tokens_in_cookies()
@validate_and_refresh_token()
def get_about_chama(request, chama_name):
    chama_id = get_chama_id(chama_name)
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }
    chama_data = requests.get(
        f"{os.getenv('api_url')}/chamas/about_chama/{chama_id}",
        headers=headers,
    )
    print("===================================")
    if chama_data.status_code == HTTPStatus.OK:
        chama = chama_details_organised(chama_data.json().get("chama"))
        rules = chama_data.json().get("rules")
        about = chama_data.json().get("about")
        faqs = chama_data.json().get("faqs")

        return render(
            request,
            "chama/about_chama.html",
            {
                "role": "manager",
                "chama": chama,
                "rules": rules,
                "about": about,
                "faqs": faqs,
            },
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def create_chama(request):
    if request.method == "POST":
        chama_name = request.POST.get("chama_name")
        chama_type = request.POST.get("chama_tags")
        no_limit = request.POST.get("noLimit")
        description = request.POST.get("description")
        registration_fee = request.POST.get("registration")
        last_joining_date = request.POST.get("last_joining_date")
        chama_category = request.POST.get("category")

        members_allowed = 0
        if no_limit == "noLimit":
            members_allowed = "infinite"
        else:
            members_allowed = request.POST.get("members_allowed")

        # Convert last and first to datetime objects and get current time
        last_joining_date = datetime.strptime(last_joining_date, "%Y-%m-%d")
        current_time_nairobi = datetime.now(nairobi_tz).replace(tzinfo=None)

        # check that last day of joining is >= today
        if last_joining_date.date() >= current_time_nairobi.date():
            data = {
                "chama_name": chama_name,
                "chama_type": chama_type,
                "description": description,
                "num_of_members_allowed": members_allowed,
                "registration_fee": registration_fee,
                "restart": False,
                "category": chama_category,
                "last_joining_date": last_joining_date.strftime("%Y-%m-%d %H:%M:%S"),
            }

            headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            }
            response = requests.post(
                f"{os.getenv('api_url')}/chamas",
                json=data,
                headers=headers,
            )

            if response.status_code == HTTPStatus.CREATED:
                messages.success(request, "Chama created successfully.")
                return redirect(reverse("manager:dashboard"))

        else:
            messages.error(request, "last joining date should not be in the past")
            return redirect(reverse("manager:dashboard"))

    return redirect(reverse("manager:dashboard"))


# create a new activity for the chama
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def create_activity(request, chama_id):
    chama_name = get_chama_name(chama_id)
    if request.method == "POST":
        activity_title = request.POST.get("activity_title")
        activity_type = request.POST.get("activity_type")
        description = request.POST.get("description")
        share_price = request.POST.get("share_price")
        fine = request.POST.get("fine")
        frequency = request.POST.get("frequency")
        weekly_day = request.POST.get("weekly_day")
        monthly_week = request.POST.get("monthly_week")
        monthly_day = request.POST.get("monthly_day")
        monthly_specific_date = request.POST.get("monthly_specific_date")
        custom_frequency = request.POST.get("custom_frequency")
        mandatory = request.POST.get("mandatory")
        last_joining_date = request.POST.get("last_joining_date")
        first_contribution_date = request.POST.get("first_contribution_date")
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        if not description:
            description = f"{activity_title}: {activity_type}"

        if (
            not activity_title
            or not activity_type
            or not description
            or not share_price
            or not fine
            or not frequency
            or not last_joining_date
            or not first_contribution_date
        ):
            messages.error(request, "All fields are required.")
            return redirect(reverse("manager:chama", args=[chama_name]))

        if len(description) > 300:
            messages.error(request, "Description should not exceed 300 characters.")
            return redirect(reverse("manager:chama", args=[chama_name]))

        # TODO: check if the first day of contribution matches the selected frequency days

        # Convert last and first to datetime objects and get current time
        last_joining_date_obj = datetime.strptime(last_joining_date, "%Y-%m-%d")
        first_contribution_date_obj = datetime.strptime(
            first_contribution_date, "%Y-%m-%d"
        )
        current_time_nairobi = datetime.now(nairobi_tz).replace(tzinfo=None)

        try:
            if (
                last_joining_date_obj.date() < current_time_nairobi.date()
                or first_contribution_date_obj.date() < current_time_nairobi.date()
            ):
                messages.error(request, "dates should not be in the past.")
                return redirect(reverse("manager:chama", args=[chama_name]))

            if first_contribution_date_obj.date() <= last_joining_date_obj.date():
                messages.error(
                    request,
                    "First contribution date should be after last joining date.",
                )
                return redirect(reverse("manager:chama", args=[chama_name]))
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect(reverse("manager:chama", args=[chama_name]))

        interval = None
        contribution_day = None

        # print("===========activity details=============")
        # print("type: ", activity_type)
        # print("last_joining_date: ", last_joining_date)
        # print("first_contribution_date: ", first_contribution_date)
        # print("frequency: ", frequency)
        # print("weekly_day: ", weekly_day)
        # print("monthly_week: ", monthly_week)
        # print("monthly_day: ", monthly_day)
        # print("monthly_specific_date: ", monthly_specific_date)
        # print("custom_frequency: ", custom_frequency)
        # print("mandatory: ", mandatory)

        if frequency == "daily":
            interval = "daily"
            contribution_day = "daily"
        elif frequency == "weekly":
            interval = "weekly"
            contribution_day = weekly_day
        elif frequency == "monthly":
            if monthly_week and monthly_day:
                interval = monthly_week
                contribution_day = monthly_day
            elif monthly_specific_date:
                interval = "monthly"
                contribution_day = monthly_specific_date
        elif frequency == "interval":
            interval = "custom"
            contribution_day = custom_frequency

        data = {
            "chama_id": chama_id,
            "activity_title": activity_title,
            "activity_type": activity_type,
            "activity_description": description,
            "activity_amount": share_price,
            "fine": fine,
            "frequency": frequency,
            "interval": interval,
            "contribution_day": contribution_day,
            "mandatory": True if mandatory else False,
            "last_joining_date": last_joining_date,
            "first_contribution_date": first_contribution_date,
        }
        creation_resp = requests.post(
            f"{os.getenv('api_url')}/activities", json=data, headers=headers
        )
        if creation_resp.status_code == HTTPStatus.CREATED:
            messages.success(request, "Activity created successfully.")
            return redirect(reverse("manager:chama", args=[chama_name]))
        else:
            messages.error(request, "An error occurred.")

    return redirect(reverse("manager:chama", args=[chama_name]))


# it gets the one chama details and displays them
@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def chama(request, key):
    # get the chama details
    chama_name = key
    chama_id = get_chama_id(chama_name)
    current_user = request.COOKIES.get("current_user")
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    chama_resp = requests.get(
        f"{os.getenv('api_url')}/managers/chama/{chama_id}", headers=headers
    )
    if chama_resp.status_code == HTTPStatus.OK:
        chama_data = chama_resp.json()["chama"]
        print("========chama access============")
        print(chama_data)
        return render(
            request,
            "manager/chamadashboard.html",
            {
                "current_user": current_user,
                "chama_name": chama_name,
                "chama_id": chama_id,
                "manager_id": chama_data["manager_id"],
                "profile_picture": chama_data["manager_profile_picture"],
                "investment_balance": chama_data["investment_balance"],
                "general_account": chama_data["general_account"],
                "total_fines": chama_data["total_fines"],
                "activities": chama_data["activities"],
            },
        )

    return redirect(reverse("manager:dashboard"))


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def chama_activity(request, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    activity_resp = requests.get(
        f"{os.getenv('api_url')}/activities/manager/{activity_id}", headers=headers
    )
    if activity_resp.status_code == HTTPStatus.OK:
        activity_dashboard = activity_resp.json()
        print("========activty access============")
        # print(activity_dashboard)
        activity_data = activity_dashboard["activity"]
        rotation_contributions = activity_dashboard["rotation_contributions"]
        chama_name = get_chama_name(activity_data["chama_id"])
        return render(
            request,
            "manager/activity_dashboard.html",
            {
                "chama_name": chama_name,
                "activity": activity_data,
                "activity_id": activity_id,
                "upcoming_rotation_date": activity_dashboard["upcoming_rotation_date"],
                "rotation_contributions": rotation_contributions,
            },
        )

    return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def profile(request, manager_id):
    full_profile = get_user_full_profile(manager_id)
    return render(request, "manager/profile.html", {"profile": full_profile})


# updating password from the profile page while logged in
@tokens_in_cookies()
@validate_and_refresh_token()
def change_password(request, manager_id):
    if request.method == "POST":
        role = request.POST.get("role")
        current_password = request.POST.get("password")
        new_password = request.POST.get("newpassword")
        confirm_password = request.POST.get("renewpassword")

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect(reverse(f"{role}:profile", args=[manager_id]))

        url = f"{os.getenv('api_url')}/users/{role}/change_password"
        data = {
            "user_id": manager_id,
            "old_password": current_password,
            "new_password": new_password,
        }
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get(f'{role}_access_token')}",
        }
        response = requests.put(url, json=data, headers=headers)

        if response.status_code == 201:
            messages.success(request, "Password changed successfully")
            return redirect(reverse(f"{role}:profile", args=[manager_id]))
        else:
            messages.error(
                request, "An error occurred or the current password is wrong"
            )
            return redirect(reverse(f"{role}:profile", args=[manager_id]))

    return redirect(reverse(f"{role}:profile", args=[manager_id]))


@tokens_in_cookies()
@validate_and_refresh_token()
def view_chama_members(request, chama_name):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    chama_id = get_chama_id(chama_name)
    chama_members = requests.get(
        f"{os.getenv('api_url')}/chamas/members/{chama_id}",
        headers=headers,
    )
    # print(chama_members.json())
    return render(
        request,
        "manager/view_members_list.html",
        {
            "chama_members": chama_members.json(),
            "chama_name": chama_name,
            "chama_id": chama_id,
        },
    )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def new_activity_members(request, activity_name, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.put(
        f"{os.getenv('api_url')}/activities/accepting_members/{activity_id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        messages.success(request, "Accepting members status updated successfully.")
    else:
        messages.error(request, "An error occurred, try again.")

    return redirect(
        reverse("member:get_about_activity", args=[activity_name, activity_id])
    )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def deactivate_activate_activity(request, activity_name, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.put(
        f"{os.getenv('api_url')}/activities/is_active/{activity_id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        messages.success(request, "Activity deactivated/activated successfully.")
    else:
        messages.error(request, "An error occurred, try again.")

    return redirect(
        reverse("member:get_about_activity", args=[activity_name, activity_id])
    )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def restart_activity(request, activity_name, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.put(
        f"{os.getenv('api_url')}/activities/restart/{activity_id}", headers=headers
    )

    if resp.status_code == HTTPStatus.OK:
        messages.success(request, "Activity restarted successfully.")
    else:
        messages.error(request, "An error occurred, try again.")

    return redirect(
        reverse("member:get_about_activity", args=[activity_name, activity_id])
    )


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def delete_activity(request, activity_id):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.delete(
        f"{os.getenv('api_url')}/activities/is_deleted/{activity_id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        messages.success(request, "Activity deleted successfully.")
    else:
        messages.error(request, "An error occurred, try again.")

    return redirect(reverse("manager:dashboard"))


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def send_invite_to_members(request, invite_to, name, id):
    if request.method == "POST":
        # get the members emails to invite, could be one or more, separated by space or comma or newline
        emails = request.POST.get("emails")
        email_list = [
            email.strip()
            for email in emails.replace("\n", ",").replace(" ", ",").split(",")
            if email.strip()
        ]

        if not email_list:
            messages.error(request, "No emails provided.")
            return redirect(reverse("member:get_about_chama", args=[name, id]))

        valid_emails = []
        invalid_emails = []

        # validate the emails
        for email in email_list:
            try:
                validate_email(email)  # django's email validator
                valid_emails.append(email)
            except ValidationError:
                invalid_emails.append(email)

        # handling valid emails
        current_year = datetime.now().year
        invite_link = f"https://chamazetu.com/member/invite/{invite_to}/{name}/{id}"
        if valid_emails:
            # send the email
            # we will call the backend here and add all these invited to the db and if successful, we send the emails
            # we will return a dictionary of emails and their invitation codes and if its an activitym we will also return the chama name it belongs to.
            context = {
                "name": name,
                "invite_link": invite_link,
                "invite_to": invite_to,
                "year": current_year,
            }
            html_content = render_to_string("chama/invitation_email.html", context)
            text_content = strip_tags(
                html_content
            )  # fallback for email clients that don't support html

            # send the email asynchronously
            send_email_invites.delay(
                valid_emails, invite_to, name, html_content, text_content
            )

        if invalid_emails:
            messages.error(request, "Invalid emails: " + ", ".join(invalid_emails))
        else:
            messages.success(request, "Invitations are being sent.")

    if invite_to == "chama":
        chama_id = id
        return redirect(reverse("member:get_about_chama", args=[name, chama_id]))
    else:
        activity_id = id
        return redirect(reverse("member:get_about_activity", args=[name, activity_id]))


async def send_activity_invite_to_all(request, invite_to, name, id):
    activity_id = id
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
    }

    resp = requests.get(
        f"{os.getenv('api_url')}/chamas/emails/{id}",
        headers=headers,
    )

    if resp.status_code == HTTPStatus.OK:
        email_list = resp.json().get("emails")
        # print("=====retrieved emails=====")
        # print(email_list)

        if not email_list:
            messages.error(request, "Error in retrieving emails.")
            return redirect(reverse("member:get_about_chama", args=[name, activity_id]))

        valid_emails = []
        invalid_emails = []

        # validate the emails
        for email in email_list:
            try:
                validate_email(email)  # django's email validator
                valid_emails.append(email)
            except ValidationError:
                invalid_emails.append(email)

        # handling valid emails
        current_year = datetime.now().year
        invite_link = (
            f"https://chamazetu.com/member/invite/{invite_to}/{name}/{activity_id}"
        )
        if valid_emails:
            context = {
                "name": name,
                "invite_link": invite_link,
                "invite_to": invite_to,
                "year": current_year,
            }
            html_content = render_to_string("chama/invitation_email.html", context)
            text_content = strip_tags(
                html_content
            )  # fallback for email clients that don't support html

            # send the email asynchronously
            send_email_invites.delay(
                valid_emails, invite_to, name, html_content, text_content
            )

            messages.success(request, "Invitations are being sent.")
    else:
        messages.error(request, "An error occurred, please try again later.")

    return redirect(reverse("member:get_about_activity", args=[name, activity_id]))
