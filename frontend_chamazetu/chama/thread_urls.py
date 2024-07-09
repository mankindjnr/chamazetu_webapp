import threading
import requests, os
import asyncio, aiohttp
from django.http import JsonResponse
from concurrent.futures import ThreadPoolExecutor, as_completed


async def fetch_chama_data(session, url, results, data=None, headers=None):
    try:
        async with session.get(url, json=data) as response:
            results[url] = {"data": await response.json(), "status": response.status}
    except Exception as e:
        results[url] = {"error": str(e)}


"""def fetch_chama_data(session, url, results, data=None, headers=None):
    if data:
        response = session.get(url, json=data, headers=headers)
    else:
        response = session.get(url, headers=headers)

    results[url] = {"data": response.json(), "status": response.status_code}"""


def fetch_data(url, results, data=None, headers=None):
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

    results[url] = {"data": response.json(), "status": response.status_code}


def is_empty_dict(item):
    return isinstance(item, dict) and len(item) == 0
