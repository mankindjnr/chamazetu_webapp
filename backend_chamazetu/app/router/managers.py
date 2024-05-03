from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from uuid import uuid4
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/managers", tags=["managers"])


# get all chamas connected to manager id
@router.get(
    "/chamas",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.ManagerChamasResp],
)
async def get_manager_chamas(
    current_user: models.Manager = Depends(oauth2.get_current_user),
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
    current_user: models.Manager = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    try:
        manager = (
            db.query(models.Manager)
            .filter(models.Manager.id == current_user.id)
            .first()
        )

        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

        return manager.profile_picture

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to get manager profile image"
        )
