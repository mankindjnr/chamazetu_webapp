import requests, jwt, json, threading, os, calendar
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.middleware.csrf import get_token
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
from django.views.decorators.csrf import csrf_exempt

from chama.decorate.tokens_in_cookies import async_tokens_in_cookies
from chama.decorate.validate_refresh_token import async_validate_and_refresh_token
from chama.chamas import get_chama_id, get_chama_number_of_members, get_chama_name, activity_chama_category
from member.members import get_user_full_profile, get_user_id

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def merry_go_round_settings(request, activity_id):
    category = await activity_chama_category(activity_id)
    return render(request, "manager/merry_go_round_settings.html", {
        "activity_id": activity_id,
        "category": category
        })

@csrf_exempt
def search_for_members_by_order_number(request, activity_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            position_one = data["position_one"]
            position_two = data["position_two"]

            if not position_one.isdigit() or not position_two.isdigit():
                return JsonResponse({"error": "Order numbers must be numbers"})

            position_one = int(position_one)
            position_two = int(position_two)

            if position_one == position_two:
                return JsonResponse({"error": "The two positions must be different."}, status=HTTPStatus.BAD_REQUEST)
            elif position_one < 1 or position_two < 1:
                return JsonResponse({"error": "The positions must be greater than 0."}, status=HTTPStatus.BAD_REQUEST)

            pulled_order_number = max(position_one, position_two)
            pushed_order_number = min(position_one, position_two)

            data = {
                "pulled_order_number": pulled_order_number,
                "pushed_order_number": pushed_order_number
            }

            url = f"{os.getenv('API_URL')}/manage_activities/search_for_members_by_order_number/{activity_id}"

            response = requests.get(url, json=data)

            if response.status_code == HTTPStatus.OK:
                members = response.json()
                return JsonResponse({"members": members}, status=HTTPStatus.OK)
            else:
                return JsonResponse({"error": response.json()["error"]}, status=response.status_code)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=HTTPStatus.BAD_REQUEST)
        except KeyError:
            return JsonResponse({"error": "No members found with those order numbers."}, status=HTTPStatus.BAD_REQUEST)

    return JsonResponse({"error": "Invalid request method."}, status=HTTPStatus.BAD_REQUEST)

@csrf_exempt
def swap_members_order_in_rotation(request, activity_id, pushed_order_number, pulled_order_number):
    if request.method == "PUT":
        try:
            if not str(pushed_order_number).isdigit() or not str(pulled_order_number).isdigit():
                return JsonResponse({"error": "Order numbers must be numbers"})
            pushed_order_number = int(pushed_order_number)
            pulled_order_number = int(pulled_order_number)

            if pulled_order_number == pushed_order_number:
                return JsonResponse({"error": "The two positions must be different."}, status=HTTPStatus.BAD_REQUEST)
            elif pulled_order_number < 1 or pushed_order_number < 1:
                return JsonResponse({"error": "The positions must be greater than 0."}, status=HTTPStatus.BAD_REQUEST)

            headers = {
                "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
                "Content-Type": "application/json"
            }

            data = {
                "pushed_order_number": pushed_order_number,
                "pulled_order_number": pulled_order_number
            }
            url = f"{os.getenv('API_URL')}/manage_activities/swap_rotation_order/{activity_id}"

            response = requests.put(url, json=data, headers=headers)

            if response.status_code == HTTPStatus.OK:
                return JsonResponse({"message": response.json()["message"]}, status=HTTPStatus.OK)
            else:
                return JsonResponse({"error": response.json()["error"]}, status=response.status_code)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=HTTPStatus.BAD_REQUEST)
        except KeyError:
            return JsonResponse({"error": "Invalid data."}, status=HTTPStatus.BAD_REQUEST)