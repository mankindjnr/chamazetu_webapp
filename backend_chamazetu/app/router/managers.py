from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytz, logging
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/managers", tags=["managers"])

nairobi_tz = ZoneInfo("Africa/Nairobi")
management_info_logger = logging.getLogger("management_info")
management_error_logger = logging.getLogger("management_error")


# the dashboard for a manager
@router.get(
    "/dashboard",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ManagerDashboardResp,
)
async def get_manager_dashboard(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        manager = (
            db.query(models.User).filter(models.User.id == current_user.id).first()
        )
        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

        # get all chamas connected to manager id
        chama_data = (
            db.query(
                models.Chama.id,
                models.Chama.chama_name,
                models.Chama.is_active,
                func.count(models.chama_user_association.c.user_id).label(
                    "member_count"
                ),
            )
            .join(
                models.chama_user_association,
                models.chama_user_association.c.chama_id == models.Chama.id,
                isouter=True,
            )
            .filter(models.Chama.manager_id == current_user.id)
            .group_by(models.Chama.id)
            .all()
        )

        chamas = [
            {
                "chama_id": chama.id,
                "chama_name": chama.chama_name,
                "member_count": chama.member_count,
                "is_active": chama.is_active,
            }
            for chama in chama_data
        ]

        # get updates and features
        updates_and_features = (
            db.query(
                models.Manager_Update_Feature.feature_title,
                models.Manager_Update_Feature.description,
                models.Manager_Update_Feature.feature_date,
            )
            .order_by(models.Manager_Update_Feature.feature_date.desc())
            .limit(5)
            .all()
        )

        updates_and_features_list = [
            {
                "feature_title": feature.feature_title,
                "feature_description": feature.feature_description,
                "feature_date": feature.feature_date,
            }
            for feature in updates_and_features
        ]

        manager_dashboard = {
            "manager_id": current_user.id,
            "current_user": manager.email,
            "manager_profile_picture": manager.profile_picture,
            "chamas": chamas,
            "updates_and_features": updates_and_features_list,
        }

        return manager_dashboard
    except Exception as e:
        management_error_logger.error(f"failed to get manager dashboard, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to get manager dashboard")


# get all chamas connected to manager id
@router.get(
    "/chamas",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.ManagerChamasResp],
)
async def get_manager_chamas(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    try:
        manager_chamas = (
            db.query(models.Chama)
            .filter(models.Chama.manager_id == current_user.id)
            .all()
        )

        return [schemas.ManagerChamasResp.from_orm(chama) for chama in manager_chamas]

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to get manager chamas")


# access chama by ID for a logged in manager
@router.get(
    "/chama/{group_id}",
    status_code=status.HTTP_200_OK,
    response_model=schemas.ChamaDashboardResp,
)
async def get_chama(
    group_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        chama = db.query(models.Chama).filter(models.Chama.id == group_id).first()
        if not chama:
            raise HTTPException(status_code=404, detail="Chama not found")

        activities = (
            db.query(models.ActivityContributionDate)
            .filter(models.ActivityContributionDate.chama_id == group_id)
            .order_by(desc(models.ActivityContributionDate.next_contribution_date))
            .all()
        )

        # total unpaid fines
        total_fines = (
            db.query(func.coalesce(func.sum(models.ActivityFine.expected_repayment), 0))
            .filter(
                and_(
                    models.ActivityFine.chama_id == group_id,
                    models.ActivityFine.is_paid == False,
                )
            )
            .scalar()
        )

        # retrieving chama investment balance
        invst_account = (
            db.query(models.Investment_Performance)
            .filter(models.Investment_Performance.chama_id == group_id)
            .first()
        )

        # retrieving chama account balance
        acct_balance = (
            db.query(models.Chama_Account)
            .filter(models.Chama_Account.chama_id == group_id)
            .first()
        )

        manager_profile = (
            db.query(models.User.profile_picture)
            .filter(models.User.id == current_user.id)
            .scalar()
        )

        # TODO: retrieve mmf activity withdrawal/ deposit history limit 3

        # organizing response data
        investment_balance = invst_account.amount_invested if invst_account else 0.0
        general_account = acct_balance.account_balance if acct_balance else 0.0
        chama_activities = [
            {
                "contribution_date": activity.next_contribution_date,
                "title": activity.activity_title,
                "type": activity.activity_type,
                "activity_id": activity.activity_id,
            }
            for activity in activities
        ]

        # return response
        return {
            "chama": {
                "manager_id": current_user.id,
                "manager_profile_picture": manager_profile,
                "investment_balance": investment_balance,
                "general_account": general_account,
                "total_fines": total_fines,
                "activities": chama_activities,
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        management_error_logger.error(f"failed to get chama by id, error: {e}")
        raise HTTPException(status_code=400, detail="Failed to retrieve chama by id")


# retrieve the lates 5 updates and features of a chama APP
@router.get(
    "/updates_and_features",
    status_code=status.HTTP_200_OK,
)
async def get_updates_and_features(
    db: Session = Depends(database.get_db),
):
    updates_and_features = (
        db.query(models.Manager_Update_Feature)
        .order_by(models.Manager_Update_Feature.feature_date.desc())
        .limit(5)
        .all()
    )

    if not updates_and_features:
        raise HTTPException(
            status_code=404, detail="No updates and features found for managers"
        )
    return updates_and_features


# get manager profile image
@router.get(
    "/profile_picture",
    status_code=status.HTTP_200_OK,
)
async def get_manager_profile_image(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    try:
        manager = (
            db.query(models.User).filter(models.User.id == current_user.id).first()
        )

        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

        return manager.profile_picture

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get manager profile image"
        )


@router.get(
    "/profile_picture/{manager_id}",
    status_code=status.HTTP_200_OK,
)
async def get_manager_profile_picture(
    manager_id: int,
    db: Session = Depends(database.get_db),
):
    try:
        manager = db.query(models.User).filter(models.User.id == manager_id).first()

        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

        return manager.profile_picture

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get manager profile image"
        )
