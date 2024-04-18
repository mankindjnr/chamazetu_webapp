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


@shared_task
def update_wallet_balance(headers, amount, chama_id, transaction_type):
    url = f"{config('api_url')}/members/update_wallet_balance"

    if transaction_type == "move_to_wallet" or transaction_type == "deposit_to_wallet":
        transaction_destination = 0  # default value for wallet
    else:
        transaction_destination = chama_id

    data = {
        "transaction_destination": int(transaction_destination),
        "amount": int(amount),
        "transaction_type": transaction_type,
    }

    response = requests.put(url, json=data, headers=headers)
    return None
