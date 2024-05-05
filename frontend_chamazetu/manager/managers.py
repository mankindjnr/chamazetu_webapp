import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta

load_dotenv()


def get_user_full_profile(role, id):
    url = f"{os.getenv('api_url')}/users/full_profile/{role}/{id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        user = resp.json()
        return user
    return None
