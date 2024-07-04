import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

load_dotenv()


def call_back_url(request):
    print("========call back data========")
    print("========call back data========")
    print("========call back data========")
    print("========call back data========")
    print("========call back data========")
    print("========call back data========")
    print("========call back data========")
    print("========call back data========")
    return JsonResponse({"message": "i am callback!"})


"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    payload = json.loads(request.body)
    # Process the callback payload here
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
"""
