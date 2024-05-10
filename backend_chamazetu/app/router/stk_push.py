import requests, os, base64
from datetime import datetime
from dotenv import load_dotenv

from .generate_token import generate_access_token

load_dotenv()


def sendStkPush(phone_number, amount, recipient, description):
    print("---------stk calling---------")
    print(phone_number)
    print(type(phone_number))
    token = generate_access_token()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    shortCode = os.getenv("SHORTCODE")
    passkey = os.getenv("PASSKEY")
    stk_password = base64.b64encode(
        (shortCode + passkey + timestamp).encode("utf-8")
    ).decode("utf-8")

    # choose one depending on you development environment
    # sandbox
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    # live
    # url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    requestBody = {
        "BusinessShortCode": shortCode,
        "Password": stk_password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",  # till "CustomerBuyGoodsOnline"
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortCode,  # paybill
        "PhoneNumber": phone_number,
        "CallBackURL": "https://chamas.southafricanorth.cloudapp.azure.com:8000/chama/callback",
        "AccountReference": recipient,  # the chamas account receiving the payment
        "TransactionDesc": description,
    }

    try:
        response = requests.post(url, json=requestBody, headers=headers)
        # the route that call this function should the use the response to call the callback url
        print(response.json())
        return response.json()
    except Exception as e:
        print("Error:", str(e))
        raise Exception("Failed to send stk push: " + str(e))
