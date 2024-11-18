import requests, jwt, json, threading, os, calendar

def add_investment():
    url = "https://20jb26ww-9400.uks1.devtunnels.ms/admin/add_to_the_marketplace"
    
    suitable_activities = [
        {"activity_type": "merry-go-round"},
        {"activity_type": "table-banking"},
        {"activity_type": "savings"},
        {"activity_type": "investment"},
        {"activity_type": "welfare"},
    ]

    data = {
        "investment_title": "Life Insurance Cover",
        "description": "Provide financial security for families with life insurance coverage.",
        "suitable_activities": suitable_activities,
    }

    add_investment_response = requests.post(url, json=data)
    if add_investment_response.status_code == 201:
        print(add_investment_response.json())
        return add_investment_response.json()
    else:
        print(add_investment_response.json())
        return None

# add_investment()

def retrieve_investment():
    url = "https://20jb26ww-9400.uks1.devtunnels.ms/chamas/investment_marketplace/2"

    retrieve_investment_response = requests.get(url)
    if retrieve_investment_response.status_code == 200:
        print(retrieve_investment_response.json())
        return retrieve_investment_response.json()
    else:
        print(retrieve_investment_response.json())
        return None

# retrieve_investment()