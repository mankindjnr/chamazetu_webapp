from __future__ import absolute_import, unicode_literals
from celery import shared_task
from decouple import config
import requests


@shared_task
def update_chama_account_balance(member_token, chama_id, amount):
    url = f"{config('api_url')}/chamas/update_account"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {member_token}",
    }

    data = {
        "chama_id": chama_id,
        "amount_deposited": amount,
    }

    response = requests.put(url, headers=headers, json=data)
    return None
