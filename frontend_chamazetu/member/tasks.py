from __future__ import absolute_import, unicode_literals
from celery import shared_task
from decouple import config
import requests


@shared_task
def update_chama_account_balance(chama_id, amount, transaction_type):
    url = f"{config('api_url')}/chamas/update_account"

    data = {
        "chama_id": chama_id,
        "amount_deposited": amount,
        "transaction_type": transaction_type,
    }

    response = requests.put(url, json=data)
    return None


@shared_task
def update_shares_number_for_member(chama_id, num_of_shares, headers):
    url = f"{config('api_url')}/chamas/update_shares"

    data = {
        "chama_id": chama_id,
        "num_of_shares": num_of_shares,
    }

    response = requests.put(url, json=data, headers=headers)
    return None
