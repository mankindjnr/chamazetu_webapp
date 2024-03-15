from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/chamas", tags=["management"])

# successful get status code


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ChamaResp)
async def create_chama(
    chama: schemas.ChamaBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):

    print("-------backend current user\n", current_user)
    chama_dict = chama.dict()
    chama_dict["manager_id"] = current_user.id
    new_chama = models.Chama(**chama_dict)
    db.add(new_chama)
    db.commit()
    db.refresh(new_chama)
    return {"Chama": [new_chama]}


@router.get("/", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp)
async def get_chama_by_name(
    chama_name: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    chama_name = chama_name["chama_name"]
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}
