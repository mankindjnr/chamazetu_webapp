from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from uuid import uuid4
from sqlalchemy import func, update, and_, table, column, desc

from .. import schemas, database, utils, oauth2, models


router = APIRouter(prefix="/search", tags=["search"])


"""# response_model=schemas.MemberSearchResp,
# search for a member in a chama
@router.get(
    "/member",
    status_code=status.HTTP_200_OK,
)
async def search_for_member(
    member_data: schemas.MemberSearchBase = Query(...),
    db: Session = Depends(database.get_db),
):

    try:
        member_dict = member_data.dict()
        chama_id = member_dict["chama_id"]
        member_name = member_dict["member_name"]

        member = (
            db.query(models.Member)
            .join(models.members_chamas_association)
            .filter(
                and_(
                    models.members_chamas_association.c.chama_id == chama_id,
                    models.Member.member_name == member_name,
                )
            )
            .first()
        )

        if member is None:
            raise HTTPException(status_code=404, detail="Member not found in the chama")

        return {"member": member}

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=400, detail="Failed to search for a member in the chama"
        )
"""
