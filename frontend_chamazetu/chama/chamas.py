import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from .rawsql import execute_sql


# we can later have  asection for chamas that are currently not acceting members so
# members can request to join/ be invited to join/ waitlist
def get_all_chamas(request, role=None):
    # TODO: replace this with a call to the backend
    query = "SELECT manager_id, chama_type, chama_name, id FROM chamas WHERE accepting_members = %s"
    params = [True]
    chamas = execute_sql(query, params)
    print("---------public chamas---------")
    print(chamas)
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

    resp = requests.get(f"http://chamazetu_backend:9400/chamas/public_chama", json=data)
    if resp.status_code == 200:
        chama = resp.json()["Chama"][0]
        print("---------public details---------")
        print(chama)
        print()
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
