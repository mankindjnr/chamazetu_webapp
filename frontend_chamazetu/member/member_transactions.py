import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from chama.rawsql import execute_sql


@tokens_in_cookies("member")
@validate_and_refresh_token("member")
def deposit_to_chama(request):
    pass
    # TODO: use the chama name and member email to get the chama id and member id before sending the deposit request to backend
    # if request.method == 'POST':
    #     amount = request.POST.get('amount')
    #     member_id = request.COOKIES.get('member_id')
    #     chama_id = request.COOKIES.get('chama_id')
    #     url = f"{config('API_URL')}/chama/deposit"
    #     headers = {
    #         "Authorization": f"Bearer {request.COOKIES.get('access_token')}"
    #     }
    #     data = {
    #         "amount": amount,
    #         "member_id": member_id,
    #         "chama_id": chama_id
    #     }
    #     response = requests.post(url, headers=headers, data=data)
    #     if response.status_code == 200:
    #         return HttpResponseRedirect(reverse('chama:chama_dashboard'))
    #     else:
    #         return HttpResponse('Failed to deposit')
    # return render(request, 'chama/deposit_to_chama.html')
