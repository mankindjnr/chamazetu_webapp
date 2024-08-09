import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


load_dotenv()


# transaction status result receiver - mpesa
@require_http_methods(["POST"])
@csrf_exempt
def status_result_receiver(request):
    print("=======status result=======")
    data = request.body.decode("utf-8")
    data = json.loads(data)
    print("=======status result=======")
    print(data)
    print()
    return JsonResponse(data)


# transaction status result timeout - mpesa
@require_http_methods(["POST"])
@csrf_exempt
def status_timeout_receiver(request):
    data = request.body.decode("utf-8")
    data = json.loads(data)
    print("=======timeout=======")
    print(data)
    return JsonResponse(data)
