from decouple import config

urls = [
    (f"{config('api_url')}/chamas/my_chamas", {}),
    (f"{config('api_url')}/members/recent_transactions", {"member_id": 2}),
    (f"{config('api_url')}/members/wallet_balance", None),
]


def is_empty_dict(item):
    return isinstance(item, dict) and len(item) == 0


for url, payload in urls:
    print(is_empty_dict(payload))
