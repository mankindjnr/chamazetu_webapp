import requests, jwt, json
from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from decouple import config

from .rawsql import execute_sql

# User management
from .usermanagement import (
    validate_token,
    refresh_token,
    signin,
    signup,
    signout,
    verify_signup_token,
    activate,
)

from .chamas import get_all_chamas


# Create your views here.
def index(request):
    return render(request, "chama/index.html")
