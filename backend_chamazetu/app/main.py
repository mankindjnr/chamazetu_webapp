import pytz
from fastapi import FastAPI
from typing import Optional
from datetime import datetime
from .logging_config import setup_logging
from app.celery import celery_app

from random import randint
from fastapi.middleware.cors import CORSMiddleware
from .router import (
    users,
    auth,
    chama_management,
    transactions,
    chama_investment,
    members,
    members_tracker,
    search_functionality,
    member_profile,
    managers,
    azure_blob_uploads,
    s3_buckets,
    newsletter,
    fines,
    callback,
    sms_callback,
    stk_push,
    activities,
    chamazetu_admin,
    table_banking,
    activity_management,
)

setup_logging()

app = FastAPI()

origins = ["*"]

"""
this will allow all origins to access the API only from the containers not from the browser
origins = [
    "http://localhost:8000",  # frontend service
    "http://localhost:9400",  # backend service
]
"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(chama_management.router)
app.include_router(transactions.router)
app.include_router(chama_investment.router)
app.include_router(members.router)
app.include_router(members_tracker.router)
app.include_router(search_functionality.router)
app.include_router(member_profile.router)
app.include_router(managers.router)
app.include_router(azure_blob_uploads.router)
app.include_router(s3_buckets.router)
app.include_router(newsletter.router)
app.include_router(fines.router)
app.include_router(callback.router)
app.include_router(stk_push.router)
app.include_router(activities.router)
app.include_router(chamazetu_admin.router)
app.include_router(sms_callback.router)
app.include_router(table_banking.router)
app.include_router(activity_management.router)

@app.get("/")
async def root():
    return {"Welcome": "to chamaZetu"}
