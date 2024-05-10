import requests, os
from dotenv import load_dotenv

load_dotenv()


def stk_push_status(checkoutrequestid):
    """
    Check the status of the stk push
    """
    data = {"checkout_request_id": checkoutrequestid}
    response = requests.get(
        f"192.168.100.7:9400/mobile_money/mpesa/stkpush/status/{checkoutrequestid}",
    )

    print("-----stk push status----")
    if response.status_code == 200:
        print("-------scceeded-----")
        print(response.json())
    print(response.json())
    return None


stk_push_status("ws_CO_09052024162348667113638169")
