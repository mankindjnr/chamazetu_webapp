import requests, json, base64, os
from dotenv import load_dotenv
from datetime import datetime
from django.http import JsonResponse
from decouple import config

load_dotenv()


def query_stk_status(checkout_request_id):
    query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        (business_short_code + os.getenv("PASSKEY") + timestamp).encode()
    ).decode()

    query_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + access_token,
    }

    query_payload = {
        "BusinessShortCode": os.getenv("SHORTCODE"),
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    try:
        response = requests.post(query_url, headers=query_headers, json=query_payload)
        response.raise_for_status()
        # Raise exception for non-2xx status codes
        response_data = response.json()

        if "ResultCode" in response_data:
            result_code = response_data["ResultCode"]
            if result_code == "1037":
                message = "1037 Timeout in completing transaction"
            elif result_code == "1032":
                message = "1032 Transaction has been canceled by the user"
            elif result_code == "1":
                message = "1 The balance is insufficient for the transaction"
            elif result_code == "0":
                message = "0 The transaction was successful"
            else:
                message = "Unknown result code: " + result_code
        else:
            message = "Error in response"

        return {"message": message, "queryResponse": response_data}
    except requests.exceptions.RequestException as e:
        print("Request error:", str(e))
        raise HTTP
    except json.JSONDecodeError as e:
        return JsonResponse(
            {"error2": "Error decoding JSON: " + str(e)}
        )  # Return JSON response for JSON decoding erro
