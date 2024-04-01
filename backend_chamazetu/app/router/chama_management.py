from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session

from .. import schemas, database, utils, oauth2, models

router = APIRouter(prefix="/chamas", tags=["management"])

# successful get status code


# create chama for a logged in manager
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.ChamaResp)
async def create_chama(
    chama: schemas.ChamaBase = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):

    print("-------backend current user\n", current_user)
    try:
        chama_dict = chama.dict()
        chama_dict["manager_id"] = current_user.id

        new_chama = models.Chama(**chama_dict)
        db.add(new_chama)
        db.commit()
        db.refresh(new_chama)

        return {"Chama": [new_chama]}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create chama")


# get chama by name for a logged in manager
@router.get("/", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp)
async def get_chama_by_name(
    chama_name: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    chama_name = chama_name["chama_name"]
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
    print("------------------------------")
    print(chama.__dict__)
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# get chama by id for a logged in member
@router.get("/chama", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp)
async def get_chama_by_id(
    chama_id: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chama_id = chama_id["chamaid"]
    print("chama_id", chama_id)
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# get chama by name for a logged in member
@router.get(
    "/chama_name", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def get_chama_by_name(
    chama_name: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chama_name = chama_name["chamaname"]
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# getting the chama for a public user - no authentication required
# TODO: the table being querries should be chama_blog/details and not chama, description should match in both
@router.get(
    "/public_chama", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def view_chama(
    chama_id: dict = Body(...),
    db: Session = Depends(database.get_db),
):
    chama_id = chama_id["chamaid"]
    chama = db.query(models.Chama).filter(models.Chama.id == chama_id).first()
    # we will use the id to extract the manager details like profile photo
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": [chama]}


# changing the status of a chama accepting new members or not
@router.put("/join_status", status_code=status.HTTP_200_OK)
async def change_chama_status(
    status: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    print("status", status)
    accepting_members = status["accepting_members"]
    chama_name = status["chama_name"]

    chama = db.query(models.Chama).filter(models.Chama.chama_name == chama_name).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    chama.accepting_members = accepting_members
    db.commit()
    return {"message": "Status updated successfully"}


# members can join chamas
@router.post("/join", status_code=status.HTTP_201_CREATED)
async def join_chama(
    chamaname: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chamaname = chamaname["chamaname"]
    chama = db.query(models.Chama).filter(models.Chama.chama_name == chamaname).first()
    if not chama:
        raise HTTPException(status_code=404, detail="Chama not found")
    chama.members.append(current_user)
    db.commit()
    return {"message": f"You have successfully joined {chamaname}"}


# members retrieving all chamas they are part of using a list of chamaids
@router.get(
    "/my_chamas", status_code=status.HTTP_200_OK, response_model=schemas.ChamaResp
)
async def my_chamas(
    chamaids: dict = Body(...),
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    chamaids = chamaids["chamaids"]
    chamas = db.query(models.Chama).filter(models.Chama.id.in_(chamaids)).all()
    if not chamas:
        raise HTTPException(status_code=404, detail="Chama not found")
    return {"Chama": chamas}
