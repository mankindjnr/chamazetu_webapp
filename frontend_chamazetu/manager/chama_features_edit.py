import requests, jwt, json, threading, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.contrib import messages
from datetime import datetime

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.chamas import get_chama_id
from member.members import get_user_id
from chama.usermanagement import (
    validate_token,
    refresh_token,
)

load_dotenv()


@tokens_in_cookies()
@validate_and_refresh_token()
def update_chama_description(request, chama_name):
    if request.method == "POST":
        chama_id = get_chama_id(chama_name)
        description = request.POST.get("description")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id, "description": description}

        response = requests.put(
            f"{os.getenv('api_url')}/chamas/update_description",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama description updated successfully.")
        else:
            messages.error(request, "Error updating chama description.")

        return redirect(
            reverse(
                f"manager:get_about_chama",
                args=[chama_name],
            )
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def update_chama_mission(request, chama_name):
    if request.method == "POST":
        chama_id = get_chama_id(chama_name)
        mission = request.POST.get("mission")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id, "mission": mission}

        response = requests.put(
            f"{os.getenv('api_url')}/chamas/update_mission",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama mission updated successfully.")
        else:
            messages.error(request, "Error updating chama mission.")

        return redirect(
            reverse(
                f"manager:get_about_chama",
                args=[chama_name],
            )
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def update_chama_vision(request, chama_name):
    if request.method == "POST":
        chama_id = get_chama_id(chama_name)
        vision = request.POST.get("vision")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id, "vision": vision}

        response = requests.put(
            f"{os.getenv('api_url')}/chamas/update_vision",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama vision updated successfully.")
        else:
            messages.error(request, "Error updating chama vision.")

        return redirect(
            reverse(
                f"manager:get_about_chama",
                args=[chama_name],
            )
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def add_chama_rules(request, chama_name):
    if request.method == "POST":
        chama_id = get_chama_id(chama_name)
        rule = request.POST.get("rule")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id, "rule": rule}

        response = requests.post(
            f"{os.getenv('api_url')}/chamas/add_rule",
            json=data,
            headers=headers,
        )

        if response.status_code == 201:
            messages.success(request, "Chama rule added successfully.")
        else:
            messages.error(request, "Error updating chama rules.")

        return redirect(
            reverse(
                f"manager:get_about_chama",
                args=[chama_name],
            )
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def delete_chama_rule(request, chama_name, rule_id):
    if request.method == "POST":
        chama_id = get_chama_id(chama_name)

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id, "rule_id": rule_id}

        response = requests.delete(
            f"{os.getenv('api_url')}/chamas/delete_rule",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama rule deleted successfully.")
        else:
            messages.error(request, "Error deleting chama rule.")

        return redirect(
            reverse(
                f"manager:get_about_chama",
                args=[chama_name],
            )
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def add_chama_faqs(request, chama_name):
    if request.method == "POST":
        chama_id = get_chama_id(chama_name)
        question = request.POST.get("question")
        answer = request.POST.get("answer")

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id, "question": question, "answer": answer}

        response = requests.post(
            f"{os.getenv('api_url')}/chamas/add_faq",
            json=data,
            headers=headers,
        )

        if response.status_code == 201:
            messages.success(request, "Chama FAQs added successfully.")
        else:
            messages.error(request, "Error updating chama FAQs.")

        return redirect(
            reverse(
                f"manager:get_about_chama",
                args=[chama_name],
            )
        )
    else:
        return redirect(reverse("manager:dashboard"))


@tokens_in_cookies()
@validate_and_refresh_token()
def delete_chama_faq(request, chama_name, faq_id):
    if request.method == "POST":
        chama_id = get_chama_id(chama_name)

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id, "faq_id": faq_id}

        response = requests.delete(
            f"{os.getenv('api_url')}/chamas/delete_faq",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama FAQ deleted successfully.")
        else:
            messages.error(request, "Error deleting chama FAQ.")

        return redirect(
            reverse(
                f"manager:get_about_chama",
                args=[chama_name],
            )
        )
    else:
        return redirect(reverse("manager:dashboard"))


# change the status of the chama to accepting members or not
@tokens_in_cookies()
@validate_and_refresh_token()
def new_members(request, chama_id, status):
    if request.method == "POST":
        chama_name = request.POST.get("chama_name")

        if status == "allow":
            status = True
        elif status == "block":
            status = False

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        data = {"chama_id": chama_id, "accepting_members": status}

        response = requests.put(
            f"{os.getenv('api_url')}/chamas/join_status",
            json=data,
            headers=headers,
        )
        if response.status_code == 200:
            if status:
                messages.success(request, f"{chama_name} is accepting members.")
            else:
                messages.success(
                    request, f"{chama_name} is no longer accepting members."
                )
            return redirect(reverse("manager:get_about_chama", args=[chama_name]))
        else:
            messages.error(request, "Error updating chama status.")
            return redirect(reverse("manager:get_about_chama", args=[chama_name]))
    else:
        return redirect(reverse("manager:dashboard"))


def activate_chama(request):
    if request.method == "POST":
        chama_id = request.POST.get("chama_id")

        is_active = True

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        data = {"chama_id": chama_id, "is_active": is_active}
        response = requests.put(
            f"{os.getenv('api_url')}/chamas/activate_deactivate",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama activated successfully.")
            return redirect(
                reverse(
                    "manager:get_about_chama",
                    args=[request.POST.get("chama_name")],
                )
            )
        else:
            messages.error(request, "Error activating chama.")
            return redirect(
                reverse(
                    "manager:get_about_chama",
                    args=[request.POST.get("chama_name")],
                )
            )
    else:
        return redirect(reverse("manager:dashboard"))


def deactivate_chama(request):
    if request.method == "POST":
        chama_id = request.POST.get("chama_id")

        is_active = False

        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }
        data = {"chama_id": chama_id, "is_active": is_active}
        response = requests.put(
            f"{os.getenv('api_url')}/chamas/activate_deactivate",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama deactivated successfully.")
            return redirect(
                reverse(
                    "manager:get_about_chama", args=[request.POST.get("chama_name")]
                )
            )
        else:
            messages.error(request, "Error deactivating chama.")
            return redirect(
                reverse(
                    "manager:get_about_chama", args=[request.POST.get("chama_name")]
                )
            )
    else:
        return redirect(reverse("manager:dashboard"))


def restart_chama(
    request,
):  # clears all data and it starts afresh, all members remain and manager as well - but he will have to set new contribution day, and change the restart chama to true
    pass


def delete_chama_by_id(request, chama_id):
    if request.method == "POST":
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('manager_access_token')}",
        }

        data = {"chama_id": chama_id}

        response = requests.delete(
            f"{os.getenv('api_url')}/chamas/delete_chama",
            json=data,
            headers=headers,
        )

        if response.status_code == 200:
            messages.success(request, "Chama deleted successfully.")
            return redirect(reverse("manager:dashboard"))
        else:
            messages.error(request, "Error deleting chama.")
            return redirect(reverse("manager:dashboard"))
