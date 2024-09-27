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
    "/profile-picture-upload/{current_user}/{user_id}",
    status_code=status.HTTP_201_CREATED,
)
async def upload_profile_picture_to_s3(
    current_user: str,
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
):

    # retrive the user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # ensure the file is a valid image type
    filename, file_extension = os.path.splitext(file.filename)
    allowed_extensions = [".jpeg", ".jpg", ".png", ".JPEG", ".JPG", ".PNG"]

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only jpg/jpeg/png files are allowed",
        )

    # reset file pointer and attempt to open the image
    file.file.seek(0)
    try:
        img = Image.open(file.file)
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        )

    # convert RGBA to RGB if necessary
    if img.mode == "RGBA":
        img = img.convert("RGB")

    # compress the image while keeping quality and sze under control
    compressed_image_io = io.BytesIO()
    img.save(compressed_image_io, format="JPEG", optimize=True, quality=85)
    compressed_image_io.seek(0)

    # check if the image is too large
    MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
    if compressed_image_io.tell() > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file too large. Must be less than 2MB",
        )

    # upload to s3
    bucket_name = os.getenv("AWS_BUCKET_NAME")
    s3_client = client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
    )

    try:
        # rewind the image bufer before uploading
        compressed_image_io.seek(0)

        s3_client.upload_fileobj(
            compressed_image_io, bucket_name, f"profile_pictures/{current_user}.jpeg"
        )
    except NoCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No credentials provided",
        )
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image",
        )

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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only jpg/jpeg/png files are allowed",
        )

    bucket_name = os.getenv("AWS_BUCKET_NAME")
    s3_client = client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
    )

    try:
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

    # update the user profile picture
    user.profile_picture = f"https://{bucket_name}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/profile_pictures/{current_user}.jpeg"
    db.commit()
    db.refresh(user)

    return {"message": "Profile picture uploaded successfully"}


@router.delete("/profile-picture-delete", status_code=status.HTTP_200_OK)
async def delete_from_s3(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
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
@router.put("/update_profile_picture", status_code=status.HTTP_200_OK)
async def update_profile_picture(
    profile: schemas.ProfilePicture,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        print("===update profile picture===")
        print(current_user.email)
        profile_picture_url = f"https://{os.getenv('AWS_BUCKET_NAME')}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/profile_pictures/{current_user.email}.jpeg"

        user = db.query(models.User).filter_by(id=current_user.id).first()

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
