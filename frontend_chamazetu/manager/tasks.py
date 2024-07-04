from __future__ import absolute_import, unicode_literals
from celery import shared_task
import requests, os, logging
from time import sleep
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

logger = logging.getLogger(__name__)


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
def update_chama_account_balance_after_withdrawals(chama_id, amount, transaction_type):
    url = f"{os.getenv('api_url')}/chamas/update_account"

    data = {
        "chama_id": chama_id,
        "amount_deposited": amount,
        "transaction_type": transaction_type,
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


# fulfill a withdrawal request- every pending request at midnight
@shared_task(
    bind=True, max_retries=3, default_retry_delay=60
)  # Retries up to 3 times with a delay of 60 seconds between retries
def fulfill_pending_withdrawal_requests(self):
    url = f"{os.getenv('api_url')}/investments/chamas/fulfill_withdrawal_requests"

    try:
        response = requests.put(url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        if response.status_code == HTTPStatus.OK:
            logging.info("Fulfilling withdrawals successful")
        else:
            logging.error(
                f"Failed to fulfill withdrawals: {response.status_code}, {response.text}"
            )
            self.retry(countdown=60)  # Retry after 60 seconds

    except requests.exceptions.RequestException as e:
        logging.error(f"Request to fulfill withdrawals failed: {e}")
        self.retry(exc=e)  # Retry on exception

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise e  # Raise the exception to be handled by Celery

    logging.info("Completed fulfill_pending_withdrawal_requests task")
