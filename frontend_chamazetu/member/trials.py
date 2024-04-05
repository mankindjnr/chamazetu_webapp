import requests
from decouple import config
from datetime import datetime

from date_trial import get_sunday_date

first_day_of_week = get_sunday_date()

data = {
    "member_id": 2,
    "chama_id": 1,
    "start_date": first_day_of_week.strftime("%Y-%m-%d"),
    "transaction_type": "deposit",
}
