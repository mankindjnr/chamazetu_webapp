from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import func, update, and_, table, column
from typing import List, Union
from zoneinfo import ZoneInfo

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

nairobi_tz = ZoneInfo("Africa/Nairobi")


@router.post(
    "/subscribe",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.NewsletterSubscriptionResp,
)
async def subscribe_to_newsletter(
    subscriber: schemas.NewsletterSubscription,
    db: Session = Depends(database.get_db),
):
    try:
        new_subscription = models.NewsletterSubscription(
            email=subscriber.email,
            date_subscribed=datetime.now(nairobi_tz).replace(tzinfo=None),
        )
        db.add(new_subscription)
        db.commit()
        db.refresh(new_subscription)

        return {
            "email": new_subscription.email,
            "date_subscribed": new_subscription.date_subscribed,
        }
    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=400, detail="Subscription failed")
