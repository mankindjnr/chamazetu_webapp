import requests
from http import HTTPStatus
import os

# this is a simple script to send sms using the textbelt api which is self hosted  as a docker container

# textbelt api key
api_key = os.getenv("TEXTBELT_API_KEY")


async def send_sms(phone_number, message):
    url = "http://localhost:9090/text"
    data = {"phone": phone_number, "message": message, "key": api_key}

    response = requests.post(url, data=data)

    if response.status_code == HTTPStatus.OK:
        return response.json()  # {"success": True, "textId": "1234567890"}
    else:
        return response.json()
