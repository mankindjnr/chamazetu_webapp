import os, base64, json, requests
from dotenv import load_dotenv

load_dotenv()


def generate_access_token():
    consumer_key = os.getenv("CONSUMER_KEY")
    consumer_secret = os.getenv("CONSUMER_SECRET")

    # choose one depending on you development environment
    # sandbox
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    # live
    # url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    try:

        encoded_credentials = base64.b64encode(
            f"{consumer_key}:{consumer_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }

        # Send the request and parse the response
        response = requests.get(url, headers=headers).json()

        # Check for errors and return the access token
        if "access_token" in response:
            print("++++++++++++++++++++")
            print(response["access_token"])
            print()
            print(response)
            return response["access_token"]
        else:
            print("---------------------")
            raise Exception(
                "Failed to get access token: " + response["error_description"]
            )
    except Exception as e:
        print("=======================")
        raise Exception("Failed to get access token: " + str(e))
