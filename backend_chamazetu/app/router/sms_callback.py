import os
from dotenv import load_dotenv

# from .sms_africastalking import send_sms

from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from sqlalchemy import func, update, and_, table, column, desc
from typing import List, Union
from sqlalchemy.exc import SQLAlchemyError

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/messages", tags=["messages"])

management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")

nairobi_tz = ZoneInfo("Africa/Nairobi")

load_dotenv()


# # deliverry reports
# @router.post("/delivery_reports", status_code=status.HTTP_201_CREATED)
# def delivery_reports(response: Response, data: schemas.DeliveryReport):
#     """
#     This endpoint is called by Africa's Talking to notify us of the delivery status of the messages we sent.
#     """
#     try:
#         print("============data============")
#         print(data)
#         print("============response============")
#         print(response)
#         print()
#         # Check if the message was successfully delivered
#         if data.status == "Success":
#             management_info_logger.info(
#                 f"Message with ID {data.id} was successfully delivered to {data.recipient}"
#             )
#         else:
#             management_error_logger.error(
#                 f"Message with ID {data.id} failed to be delivered to {data.recipient}"
#             )

#         return {"message": "Delivery report received successfully"}
#     except Exception as e:
#         management_error_logger.error(f"Failed to process delivery report due to: {e}")
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"message": f"Failed to process delivery report due to: {e}"}
