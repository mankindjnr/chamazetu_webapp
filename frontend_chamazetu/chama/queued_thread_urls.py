import threading
import requests
from django.http import JsonResponse
from queue import Queue


def fetch_queued_data(url, queue, data=None, headers=None):
    if data and headers:
        response = requests.get(url, json=data, headers=headers)
    elif data:
        response = requests.get(url, json=data)
    elif headers:
        response = requests.get(url, headers=headers)
    elif is_empty_dict(data) and headers:
        response = requests.get(url, headers=headers)
    else:
        response = requests.get(url)

    queue.put({url: {"data": response.json(), "status": response.status_code}})


def is_empty_dict(item):
    return isinstance(item, dict) and len(item) == 0
