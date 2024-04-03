import threading
import requests
from django.http import JsonResponse


def fetch_data(url, data, headers, results):
    response = requests.get(url, json=data, headers=headers)
    results[url] = {"data": response.json(), "status": response.status_code}
