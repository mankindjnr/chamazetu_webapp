import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from .rawsql import execute_sql


# we can later have  asection for chamas that are currently not acceting members so
# members can request to join/ be invited to join/ waitlist
def get_all_chamas(request):
    query = "SELECT chama_name, manager_id FROM chamas WHERE accepting_members = %s"
    params = [True]
    chamas = dict(execute_sql(query, params))
    print("---------public chamas---------")
    print(chamas)
    return render(
        request,
        "chama/allchamas.html",
        {
            "chamas": chamas,
        },
    )
