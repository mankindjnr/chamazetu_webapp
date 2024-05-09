import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

load_dotenv()


def call_back_url(request):
    print("========call back data========")
    if request.method != "POST":
        return HttpResponse(status=405)

    callback_data = json.loads(request.body)
    print("========cala back data========")
    print(callback_data)

    result_code = callback_data["Body"]["stkCallback"]["ResultCode"]
    if result_code != 0:
        # this is an error
        error_message = callback_data["Body"]["stkCallback"]["ResultDesc"]
        response_data = {
            "ResultCode": result_code,
            "ResultDesc": error_message,
        }
        return response_data

    # else the transaction was successful
    callback_metadata = callback_data["Body"]["stkCallback"]["CallbackMetadata"]
    amount = None
    phone_number = None
    for item in callback_metadata["Item"]:
        if item["Name"] == "Amount":
            amount = item["Value"]
        if item["Name"] == "PhoneNumber":
            phone_number = item["Value"]
    print("------------------------------")
    print(f"Amount: {amount}, Phone Number: {phone_number}")
    # save the transaction details to a db
    # f"{os.getenv('api_url')}/mobile_money/mpesa/callback"

    # send a response to the mpesa api
    response_data = {
        "ResultCode": result_code,
        "ResultDesc": "Success",
    }

    return response_data
