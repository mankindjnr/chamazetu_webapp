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


@csrf_exempt
@require_http_methods(["POST"])
def call_back(request):
    payload = json.loads(request.body)
    url = f"{os.getenv('api_url')}/callback/data"
    # add a status field to the payload, default is not processed- - bg task will update this after checking the payment status
    print("====================================")
    print(payload)
    data = {
        "MerchantRequestID": payload["Body"]["stkCallback"]["MerchantRequestID"],
        "CheckoutRequestID": payload["Body"]["stkCallback"]["CheckoutRequestID"],
        "ResultCode": payload["Body"]["stkCallback"]["ResultCode"],
        "ResultDesc": payload["Body"]["stkCallback"]["ResultDesc"],
        "Amount": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0][
            "Value"
        ],
        "MpesaReceiptNumber": payload["Body"]["stkCallback"]["CallbackMetadata"][
            "Item"
        ][1]["Value"],
        "TransactionDate": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][
            3
        ]["Value"],
        "PhoneNumber": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][4][
            "Value"
        ],
    }

    response = requests.post(url, json=data)
    # Process the callback payload here
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})


@csrf_exempt
@require_http_methods(["POST"])
def registration_call_back(request):
    payload = json.loads(request.body)
    url = f"{os.getenv('api_url')}/callback/registration"
    data = {
        "MerchantRequestID": payload["Body"]["stkCallback"]["MerchantRequestID"],
        "CheckoutRequestID": payload["Body"]["stkCallback"]["CheckoutRequestID"],
        "ResultCode": payload["Body"]["stkCallback"]["ResultCode"],
        "ResultDesc": payload["Body"]["stkCallback"]["ResultDesc"],
        "Amount": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0][
            "Value"
        ],
        "MpesaReceiptNumber": payload["Body"]["stkCallback"]["CallbackMetadata"][
            "Item"
        ][1]["Value"],
        "TransactionDate": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][
            3
        ]["Value"],
        "PhoneNumber": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][4][
            "Value"
        ],
    }

    # run three times on failure
    response = requests.post(url, json=data)

    # Process the callback payload here
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})


def call_back(request):
    payload = json.loads(request.body)
    url = f"{os.getenv('api_url')}/callback/data"
    # add a status field to the payload, default is not processed- - bg task will update this after checking the payment status
    print("====================================")
    print(payload)
    data = {
        "MerchantRequestID": payload["Body"]["stkCallback"]["MerchantRequestID"],
        "CheckoutRequestID": payload["Body"]["stkCallback"]["CheckoutRequestID"],
        "ResultCode": payload["Body"]["stkCallback"]["ResultCode"],
        "ResultDesc": payload["Body"]["stkCallback"]["ResultDesc"],
        "Amount": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][0][
            "Value"
        ],
        "MpesaReceiptNumber": payload["Body"]["stkCallback"]["CallbackMetadata"][
            "Item"
        ][1]["Value"],
        "TransactionDate": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][
            3
        ]["Value"],
        "PhoneNumber": payload["Body"]["stkCallback"]["CallbackMetadata"]["Item"][4][
            "Value"
        ],
    }

    response = requests.post(url, json=data)
    # Process the callback payload here
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
