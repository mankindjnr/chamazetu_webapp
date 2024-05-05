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


# check if its possible to call other background tasks inside a background task - to update the account balance while updating the investment balance
