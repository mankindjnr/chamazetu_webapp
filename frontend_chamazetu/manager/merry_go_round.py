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

from chama.decorate.tokens_in_cookies import async_tokens_in_cookies
from chama.decorate.validate_refresh_token import async_validate_and_refresh_token
from chama.chamas import get_chama_id, get_chama_number_of_members, get_chama_name
from member.members import get_user_full_profile, get_user_id

load_dotenv()

nairobi_tz = ZoneInfo("Africa/Nairobi")

@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def merry_go_round_settings(request, activity_id):
    return render(request, "manager/merry_go_round_settings.html", {"activity_id": activity_id})