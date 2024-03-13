from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/chamas", tags=["management"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ChamaResp)
async def create_chama(
    chama: schemas.ChamaBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    chama_dict = chama.dict()
    chama_dict["manager_id"] = current_user.id
    new_chama = models.Chama(**chama_dict)
    db.add(new_chama)
    db.commit()
    db.refresh(new_chama)
    return {"Chama": [new_chama]}
