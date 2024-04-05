import threading
import requests
from django.http import JsonResponse


def fetch_data(url, results, data=None, headers=None):
    if data and headers:
        response = requests.get(url, json=data, headers=headers)
    elif data:
        response = requests.get(url, json=data)
    elif headers:
        response = requests.get(url, headers=headers)
    else:
        response = requests.get(url)

    results[url] = {"data": response.json(), "status": response.status_code}
