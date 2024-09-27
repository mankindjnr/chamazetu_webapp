import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timedelta
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from http import HTTPStatus

from chama.decorate.tokens_in_cookies import tokens_in_cookies, async_tokens_in_cookies
from chama.decorate.validate_refresh_token import (
    validate_and_refresh_token,
    async_validate_and_refresh_token,
)
from .members import get_user_id
from .tasks import update_users_profile_image

load_dotenv()

MAX_FILE_SIZE_MB = 2
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


@async_tokens_in_cookies()
@async_validate_and_refresh_token()
async def update_profile_image(request):
    print("======profile_updater======")
    if request.method == "POST":
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        user_id = get_user_id(request.COOKIES.get(f"current_user"))

        new_profile_image = (
            request.FILES.get("profile_image")
            if "profile_image" in request.FILES
            else None
        )
        if new_profile_image:
            # ensure file size id under 2mb before processing
            if new_profile_image.size > MAX_FILE_SIZE_BYTES:
                messages.error(
                    request, f"File size should be less than {MAX_FILE_SIZE_MB}MB"
                )
                return redirect(
                    reverse(
                        "member:profile",
                        args=[user_id],
                    )
                )

            # open the image
            img = Image.open(new_profile_image)
            if img.mode == "RGBA":
                img = img.convert("RGB")

            # resize the image
            byte_arr = BytesIO()
            quality = 85  # starting with a high quality image
            img.save(byte_arr, format="JPEG", quality=quality)
            byte_arr_size = byte_arr.tell()

            # reduce the quality of the image if the size is still too large
            while byte_arr_size > MAX_FILE_SIZE_BYTES and quality > 10:
                quality -= 5
                byte_arr = BytesIO()
                img.save(byte_arr, format="JPEG", quality=quality)
                byte_arr_size = byte_arr.tell()

            if byte_arr_size > MAX_FILE_SIZE_BYTES:
                messages.error(
                    request, f"File size should be less than {MAX_FILE_SIZE_MB}MB"
                )
                return redirect(
                    reverse(
                        "member:profile",
                        args=[user_id],
                    )
                )

            byte_arr.seek(0)

            # create a new django file-like object to use in your upload
            updated_profile_image = InMemoryUploadedFile(
                byte_arr,
                "image_field",
                f"{new_profile_image.name}.jpeg",
                "image/jpeg",
                byte_arr.getbuffer().nbytes,
                None,
            )

            # send the image to the api
            url = f"{os.getenv('api_url')}/bucket-uploads/profile-picture-upload/{request.COOKIES.get(f'current_user')}/{user_id}"
            files = {"file": (updated_profile_image.name, byte_arr, "image/jpeg")}
            response = requests.post(url, files=files)
            if response.status_code == HTTPStatus.CREATED:
                messages.success(request, "Profile image updated successfully")
            else:
                messages.error(request, "Failed to update profile image")

            return redirect(
                reverse(
                    "member:profile",
                    args=[user_id],
                )
            )

    return redirect(
        reverse(
            "member:profile",
            args=[get_user_id(request.COOKIES.get(f"current_user"))],
        )
    )


def update_phone_number(request, user_id):
    if request.method == "POST":
        new_phone_number = request.POST.get("phone_number").strip().replace(" ", "")
        if len(new_phone_number) == 10:
            headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
            }
            url = f"{os.getenv('api_url')}/users/update_phone_number"
            data = {"phone_number": new_phone_number[1:]}
            response = requests.put(url, json=data, headers=headers)
            if response.status_code == HTTPStatus.OK:
                messages.success(request, "Phone number updated successfully")
                return redirect(reverse("member:profile", args=[user_id]))
            else:
                messages.error(request, "Failed to update phone number")
                return redirect(reverse("member:profile", args=[user_id]))
        else:
            messages.error(request, "Phone number must be 10 digits")
            return redirect(reverse("member:profile", args=[user_id]))
    return redirect(reverse("member:profile", args=[user_id]))


# TODO: find a way to check if the twitter handle is valid
def update_twitter_handle(request, user_id):
    if request.method == "POST":
        new_twitter_handle = request.POST.get("twitter_handle").strip().replace(" ", "")
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        if len(new_twitter_handle) > 0:
            url = f"{os.getenv('api_url')}/users/update_twitter_handle"
            data = {"twitter": new_twitter_handle}
            response = requests.put(url, json=data, headers=headers)
            if response.status_code == HTTPStatus.OK:
                messages.success(request, "Twitter handle updated successfully")
            else:
                messages.error(request, "Failed to update twitter handle")
        else:
            messages.error(request, "Twitter handle cannot be empty")

        return redirect(reverse("member:profile", args=[user_id]))
    return redirect(reverse("member:profile", args=[user_id]))


def update_facebook_handle(request, user_id):
    if request.method == "POST":
        new_facebook_handle = (
            request.POST.get("facebook_handle").strip().replace(" ", "")
        )
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        if len(new_facebook_handle) > 0:
            url = f"{os.getenv('api_url')}/users/update_facebook_handle"
            data = {"facebook": new_facebook_handle}
            response = requests.put(url, json=data, headers=headers)
            if response.status_code == 200:
                messages.success(request, "Facebook handle updated successfully")
            else:
                messages.error(request, "Failed to update facebook handle")
        else:
            messages.error(request, "Facebook handle cannot be empty")

        return redirect(reverse("member:profile", args=[user_id]))
    return redirect(reverse("member:profile", args=[user_id]))


def update_linkedin_handle(request, user_id):
    if request.method == "POST":
        new_linkedin_handle = (
            request.POST.get("linkedin_handle").strip().replace(" ", "")
        )
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }
        if len(new_linkedin_handle) > 0:
            url = f"{os.getenv('api_url')}/users/update_linkedin_handle"
            data = {"linkedin": new_linkedin_handle}
            response = requests.put(url, json=data, headers=headers)
            if response.status_code == HTTPStatus.OK:
                messages.success(request, "Linkedin handle updated successfully")
            else:
                messages.error(request, "Failed to update linkedin handle")
        else:
            messages.error(request, "Linkedin handle cannot be empty")

        return redirect(reverse("member:profile", args=[user_id]))
    return redirect(reverse("member:profile", args=[user_id]))
