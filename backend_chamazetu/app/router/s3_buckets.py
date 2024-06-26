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
import io, os, gzip
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from .. import schemas, database, utils, oauth2, models

from boto3 import client
from botocore.exceptions import NoCredentialsError, ClientError

router = APIRouter(prefix="/bucket-uploads", tags=["uploads"])

load_dotenv()


def compress_file(file):
    compressed_file = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_file, mode="w") as f:
        f.write(file.read())
    compressed_file.seek(0)
    return compressed_file


def object_exists(bucket_name, key):
    try:
        s3_client.head_object(Bucket=bucket_name, Key=key)
        return True
    except ClientError:
        return False


@router.post(
    "/profile-picture-upload/{current_user}", status_code=status.HTTP_201_CREATED
)
async def upload_profile_picture_to_s3(
    current_user: str,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
):
    print("===image uploads====")
    # change image to RGB IF it is RGBA
    file.file.seek(0)
    try:
        img = Image.open(file.file)
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )
    if img.mode == "RGBA":
        img = img.convert("RGB")

    # save the image to a file in memory
    img_io = io.BytesIO()
    img.save(img_io, format="JPEG")
    img_io.seek(0)

    filename, file_extension = os.path.splitext(file.filename)
    if file_extension not in [".jpeg", ".jpg", ".png", ".JPEG", ".JPG", ".PNG"]:
        print("===image if sector====")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only jpg/jpeg/png files are allowed",
        )
    print("=======================")

    bucket_name = os.getenv("AWS_BUCKET_NAME")
    s3_client = client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
    )

    try:
        print("====try sector====")
        print(f"Uploading to s3 buckets {file.filename}")

        # resize the image
        compressed_image_io = io.BytesIO()
        image = Image.open(img_io)
        image.save(compressed_image_io, format="JPEG", optimize=True)
        compressed_image_io.seek(0)

        s3_client.upload_fileobj(
            compressed_image_io, bucket_name, f"profile_pictures/{current_user}.jpeg"
        )
    except NoCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No credentials provided",
        )

    return {"file_name": current_user, "status": "uploaded"}


@router.delete("/profile-picture-delete", status_code=status.HTTP_200_OK)
async def delete_from_s3(
    db: Session = Depends(database.get_db),
    current_user: Union[models.Member, models.Manager] = Depends(
        oauth2.get_current_user
    ),
):
    bucket_name = os.getenv("AWS_BUCKET_NAME")
    s3_client = client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
    )

    try:
        s3_client.delete_object(
            Bucket=bucket_name, Key=f"profile_pictures/{current_user.email}.jpeg"
        )
    except NoCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No credentials provided",
        )

    return {"message": "Profile picture deleted successfully"}


# update profile pictre column for member/manager
@router.put("/manager/update_profile_picture", status_code=status.HTTP_201_CREATED)
async def update_profile_picture(
    profile: schemas.ProfilePicture,
    db: Session = Depends(database.get_db),
    current_user: models.Manager = Depends(oauth2.get_current_user),
):
    try:
        print("===update profile picture===")
        print(current_user.email)
        profile_picture_url = f"https://{os.getenv('AWS_BUCKET_NAME')}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/profile_pictures/{current_user.email}.jpeg"

        user = db.query(models.Manager).filter_by(id=current_user.id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found",
            )

        user.profile_picture = profile_picture_url
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile picture not updated",
        )


@router.put("/member/update_profile_picture", status_code=status.HTTP_201_CREATED)
async def update_profile_picture(
    profile: schemas.ProfilePicture,
    db: Session = Depends(database.get_db),
    current_user: models.Member = Depends(oauth2.get_current_user),
):
    try:
        print("===update profile picture===")
        profile_picture_url = f"https://{os.getenv('AWS_BUCKET_NAME')}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/profile_pictures/{profile.profile_picture_name}.jpeg"

        user = db.query(models.Member).filter_by(id=current_user.id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found",
            )

        user.profile_picture = profile_picture_url
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile picture not updated",
        )
