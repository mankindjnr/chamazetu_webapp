from fastapi import FastAPI
from typing import Optional
from random import randint
from fastapi.middleware.cors import CORSMiddleware
from .router import (
    users,
    auth,
    test,
    chama_management,
    transactions,
    chama_investment,
    members,
    members_tracker,
    search_functionality,
    member_profile,
    managers,
    azure_blob_uploads,
    daraja_api,
)

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(test.router)
app.include_router(chama_management.router)
app.include_router(transactions.router)
app.include_router(chama_investment.router)
app.include_router(members.router)
app.include_router(members_tracker.router)
app.include_router(search_functionality.router)
app.include_router(member_profile.router)
app.include_router(managers.router)
app.include_router(azure_blob_uploads.router)
app.include_router(daraja_api.router)


@app.get("/")
async def root():
    return {"Welcome": "to chamaZetu"}
