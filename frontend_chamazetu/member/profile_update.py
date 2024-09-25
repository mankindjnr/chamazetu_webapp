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

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from .members import get_user_id
from .tasks import update_users_profile_image

load_dotenv()


@tokens_in_cookies()
@validate_and_refresh_token()
def profile_updater(request):
    print("======profile_updater======")
    if request.method == "POST":
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get('access_token')}",
        }

        new_number = (
            request.POST.get("phone")
            if request.POST.get("phone") != "N/A" and request.POST.get("phone") != ""
            else None
        )
        new_twitter = (
            request.POST.get("twitter")
            if request.POST.get("twitter") != "N/A"
            else None
        )
        new_facebook = (
            request.POST.get("facebook")
            if request.POST.get("facebook") != "N/A"
            else None
        )
        new_linkedin = (
            request.POST.get("linkedin")
            if request.POST.get("linkedin") != "N/A"
            else None
        )
        new_profile_image = (
            request.FILES.get("profile_image")
            if "profile_image" in request.FILES
            else None
        )
        if new_profile_image:
            # open the image
            img = Image.open(new_profile_image)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            # resize the image
            byte_arr = BytesIO()
            img.save(byte_arr, format="JPEG", quality=20)
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

            # new_profile_image = request.FILES["profile_image"]
            url = f"{os.getenv('api_url')}/bucket-uploads/profile-picture-upload/{request.COOKIES.get(f'current_user')}"
            files = {"file": (updated_profile_image.name, byte_arr, "image/jpeg")}
            print("======new_profile_image=====")
            print(files)
            response = requests.post(url, files=files)
            if response.status_code == HTTPStatus.Created:
                print("======return from update profile image=====")
                print(response.json())
                update_users_profile_image.delay(headers, response.json()["file_name"])
                messages.success(request, "Profile image updated successfully")
            else:
                messages.error(request, "Failed to update profile image")

        user = request.COOKIES.get(f"current_user")
        user_id = get_user_id(user)

        if new_number:
            update_phone_number(request, new_number, headers, user_id)
        if new_twitter:
            update_twitter_handle(request, new_twitter, headers, user_id)
        if new_facebook:
            update_facebook_handle(request, new_facebook, headers, user_id)
        if new_linkedin:
            update_linkedin_handle(request, new_linkedin, headers, user_id)

    return redirect(
        reverse(
            "member:profile",
            args=[get_user_id(request.COOKIES.get(f"current_user"))],
        )
    )


def update_phone_number(request, new_phone_number, headers, user_id):
    if len(new_phone_number) == 9:
        new_phone_number = new_phone_number.replace(" ", "")
        url = f"{os.getenv('api_url')}/users/update_phone_number"
        data = {"phone_number": new_phone_number}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Phone number updated successfully")
            return redirect(reverse("member:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update phone number")
            return redirect(reverse("member:profile", args=[user_id]))
    else:
        messages.error(request, "Phone number must be 9 digits")
        return redirect(reverse("member:profile", args=[user_id]))


# TODO: find a way to check if the twitter handle is valid
def update_twitter_handle(request, new_twitter_handle, headers, user_id):
    if len(new_twitter_handle) > 0:
        new_twitter_handle = new_twitter_handle.replace(" ", "")
        url = f"{os.getenv('api_url')}/users/update_twitter_handle"
        data = {"twitter": new_twitter_handle}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Twitter handle updated successfully")
            return redirect(reverse("member:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update twitter handle")
            return redirect(reverse("member:profile", args=[user_id]))
    else:
        messages.error(request, "Twitter handle cannot be empty")
        return redirect(reverse("member:profile", args=[user_id]))


def update_facebook_handle(request, new_facebook_handle, headers, user_id):
    if len(new_facebook_handle) > 0:
        new_facebook_handle = new_facebook_handle.replace(" ", "")
        url = f"{os.getenv('api_url')}/users/update_facebook_handle"
        data = {"facebook": new_facebook_handle}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            messages.success(request, "Facebook handle updated successfully")
            return redirect(reverse("member:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update facebook handle")
            return redirect(reverse("member:profile", args=[user_id]))
    else:
        messages.error(request, "Facebook handle cannot be empty")
        return redirect(reverse("member:profile", args=[user_id]))


def update_linkedin_handle(request, new_linkedin_handle, headers, user_id):
    if len(new_linkedin_handle) > 0:
        new_linkedin_handle = new_linkedin_handle.replace(" ", "")
        url = f"{os.getenv('api_url')}/users/update_linkedin_handle"
        data = {"linkedin": new_linkedin_handle}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == HTTPStatus.OK:
            messages.success(request, "Linkedin handle updated successfully")
            return redirect(reverse("member:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update linkedin handle")
            return redirect(reverse("member:profile", args=[user_id]))
    else:
        messages.error(request, "Linkedin handle cannot be empty")
        return redirect(reverse("member:profile", args=[user_id]))
