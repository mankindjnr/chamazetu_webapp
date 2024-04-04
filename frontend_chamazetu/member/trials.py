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

print(data)
print()

response = requests.get("http://127.0.0.1:9400/transactions/weekly", json=data)
print(response.status_code)
print()
print(response.json())

# today_date = datetime.now().date()
# print(today_date)

# today_name = today_date.strftime("%A")
# print(today_name)
