from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Response,
    Body,
    UploadFile,
    File,
)
from typing import Union
from PIL import Image
import io, os
from uuid import uuid4
from sqlalchemy.orm import Session
from decouple import config
from .. import schemas, database, utils, oauth2, models

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

router = APIRouter(prefix="/uploads", tags=["uploads"])


connection_string = config("AZURE_STORAGE_CONNECTION_STRING_1")


# Create a unique name for the container
profile_container_name = "chamazetu-profiles"


@router.put("/{role}/update_profile_image/", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
):
    print("===image uploads====")
    if not file:
        print("===image if sector====")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File or User not found",
        )
    else:
        print("===image uploads else sector====")
        # Create a BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

        # Create a blob client using the local file name as the name for the blob
        new_filename = str(uuid4()) + file.filename
        blob_client = blob_service_client.get_blob_client(
            container=profile_container_name, blob=new_filename
        )

        try:
            print("====try sector====")
            print(f"Uploading to Azure Storage as blob: {file.filename}")

            # read the image file
            image_data = await file.read()
            # open the image file
            img = Image.open(io.BytesIO(image_data))

            # resize the image
            compressed_image_io = io.BytesIO()
            img.save(compressed_image_io, format="JPEG", optimize=True, quality=20)
            compressed_image_io.seek(0)

            # upload the image to azure blob storage
            blob_client.upload_blob(compressed_image_io, overwrite=True)
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File not uploaded",
            )
        finally:
            await file.close()

        return {"file_name": new_filename, "status": "uploaded"}


# update profile pictre column for member/manager
@router.put("/{role}/update_profile_picture", status_code=status.HTTP_201_CREATED)
async def update_profile_picture(
    role: str,
    profile: schemas.ProfilePicture,
    db: Session = Depends(database.get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):
    print("===update profile picture===")
    profile_picture_url = f"https://{config('AZURE_PROFILE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net/{profile_container_name}/{profile.profile_picture_name}"
    user = None
    if role == "member":
        user = db.query(models.Member).filter_by(id=current_user.id).first()
    elif role == "manager":
        user = db.query(models.Manager).filter_by(id=current_user.id).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )
    else:
        print("===update profile picture else sector===")
        # deleting the previous profile picture
        if user.profile_picture:
            blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
            blob_client = blob_service_client.get_blob_client(
                container=profile_container_name,
                blob=os.path.basename(user.profile_picture),
            )
            blob_client.delete_blob()

        user.profile_picture = profile_picture_url
        db.commit()
        db.refresh(user)
        return user
