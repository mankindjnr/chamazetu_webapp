import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse

load_dotenv()

# User management
from .usermanagement import (
    validate_token,
    refresh_token,
    signin,
    signup,
    signout,
    verify_signup_token,
    activate,
    forgot_password,
    update_forgotten_password,
    join_newsletter,
)

from .chamas import get_all_chamas, get_chama
from .callback import call_back, registration_call_back
from .transaction_status import status_result_receiver, status_timeout_receiver


# Create your views here.
def index(request):
    return render(request, "chama/index.html")
