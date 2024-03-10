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
    memberdashboard,
    managerdashboard,
    profile,
    signin,
    signup,
    verify_signup_token,
    activate,
)


# Create your views here.
def index(request):
    return render(request, "chama/index.html")
