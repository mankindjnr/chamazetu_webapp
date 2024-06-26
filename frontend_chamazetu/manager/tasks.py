from __future__ import absolute_import, unicode_literals
from celery import shared_task
import requests, os
from dotenv import load_dotenv

load_dotenv()


@shared_task
def update_investment_account(chama_id, amount, investment_type, transaction_type):
    url = f"{os.getenv('api_url')}/investments/chamas/update_investment_account"
    data = {
        "amount_invested": amount,
        "investment_type": investment_type,
        "transaction_type": transaction_type,
        "chama_id": chama_id,
    }

    response = requests.put(url, json=data)
    return None


@shared_task
def add_chama_withdrawal_request(chama_id, amount, headers):
    url = f"{os.getenv('api_url')}/investments/chamas/withdrawal_requests"
    data = {
        "withdrawal_amount": amount,
        "chama_id": chama_id,
    }

    response = requests.post(url, headers=headers, json=data)
    return None


# fulfill a withdrawal request- every pending request after 24 hours
@shared_task
def fulfill_pending_withdrawal_requests(chama_id, amount):
    url = f"{os.getenv('api_url')}/chamas/fulfill_withdrawal_request"
    data = {"chama_id": chama_id, "amount_withdrawn": amount}

    response = requests.put(url, json=data)
    return None
