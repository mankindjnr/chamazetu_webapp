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


@app.get("/")
async def root():
    return {"Welcome": "to chamaZetu"}
