import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from django.contrib import messages
import threading

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql
from chama.chamas import get_chama_id
from chama.thread_urls import fetch_data

from chama.usermanagement import (
    validate_token,
    refresh_token,
)


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def view_chama(request, chamaid):
    data = {"chamaid": chamaid}
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }
    resp = requests.get(f"{config('api_url')}/chamas/chama", json=data, headers=headers)
    if resp.status_code == 200:
        chama = resp.json()["Chama"][0]
        print("---------chama details---------")
        print(chama)
        print()

        return render(
            request,
            "chama/blog_chama.html",
            {
                "role": "member",
                "chama": chama,
            },
        )


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def access_chama(request, chamaname):
    chama_id = get_chama_id(chamaname)

    urls = [
        f"{config('api_url')}/chamas/chama_name",
        f"{config('api_url')}/transactions/{chamaname}",
    ]

    results = {}
    threads = []

    data_payload = [
        {"chamaname": chamaname},  # first url
        {"chama_id": chama_id},  # second url
    ]
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
    }
    # create and start a thread for each url
    for idx, url in enumerate(urls):
        thread = threading.Thread(
            target=fetch_data, args=(url, data_payload[idx], headers, results)
        )
        threads.append(thread)
        thread.start()

    # wait for all threads to finish
    for thread in threads:
        thread.join()

    # process the results of the threads
    if results[urls[0]]["status"] == 200:
        chama = results[urls[0]]["data"]["Chama"][0]
        transactions = []
        if results[urls[1]]["status"] == 200:
            if len(results[urls[1]]["data"]) > 0:
                transactions = results[urls[1]]["data"]
                print("---------chama transactions---------")
                print(transactions)
        return render(
            request,
            "member/chamadashboard.html",
            {
                "current_user": request.COOKIES.get("current_member"),
                "role": "member",
                "chama": chama,
                "transactions": transactions,
            },
        )
    else:
        return render(request, "member/chamadashboard.html")


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def join_chama(request):
    if request.method == "POST":
        data = {
            "chamaname": request.POST.get("chamaname"),
            "member": request.COOKIES.get("current_member"),
        }
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('member_access_token')}",
        }
        resp = requests.post(
            f"{config('api_url')}/chamas/join", json=data, headers=headers
        )
        if resp.status_code == 201:
            return HttpResponseRedirect(reverse("member:dashboard"))
        elif resp.status_code == 400:
            messages.error(request, f"you are already a member of {data['chamaname']}")
            return HttpResponseRedirect(
                reverse("chama:chamas", args={"role": "member"})
            )
        else:
            messages.error(request, "Failed to join chama")
            chama_id = get_chama_id(request.POST.get("chamaname"))
            return HttpResponseRedirect(
                reverse("chama:chamas", args={"role": "member"})
            )

    return HttpResponseRedirect(reverse("chama:chamas", args={"role": "member"}))
