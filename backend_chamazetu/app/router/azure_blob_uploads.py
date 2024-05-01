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
from decouple import config
from .. import schemas, database, utils, oauth2, models

from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

router = APIRouter(prefix="/uploads", tags=["uploads"])


connection_string = config("STORAGE_CONNECTION_STRING_1")
test_connection_string = config("TEST_CONNECTION_STRING_1")
test_key_1 = config("TEST_KEY_1")

# Create a unique name for the container
profile_container_name = "chamazetu-uploads-one"
test_container_name = "chamazetu-uploads-test"


@router.put("/{role}/update_profile_image/")
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
        blob_client = blob_service_client.get_blob_client(
            container=profile_container_name, blob=file.filename
        )

        try:
            print("====try sector====")
            print(f"Uploading to Azure Storage as blob: {file.filename}")
            blob_data = await file.read()
            blob_client.upload_blob(blob_data, overwrite=True)
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File not uploaded",
            )
        finally:
            await file.close()

        return {"message": "File uploaded successfully"}


@router.put("/{role}/uploads/")
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
            test_connection_string
        )

        # Create a blob client using the local file name as the name for the blob
        blob_client = blob_service_client.get_blob_client(
            container=test_container_name, blob=file.filename
        )

        try:
            print("====try sector====")
            print(f"Uploading to Azure Storage as blob: {file.filename}")
            blob_data = await file.read()
            blob_client.upload_blob(blob_data, overwrite=True)
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File not uploaded",
            )
        finally:
            await file.close()

        return {"message": "File uploaded successfully"}
