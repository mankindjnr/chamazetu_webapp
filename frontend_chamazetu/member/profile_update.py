import requests, jwt, json, os
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config
from datetime import datetime, timedelta

from chama.decorate.tokens_in_cookies import tokens_in_cookies
from chama.decorate.validate_refresh_token import validate_and_refresh_token
from .members import get_user_id


def profile_updater(request, role):
    if request.method == "POST":
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.COOKIES.get(f'{role}_access_token')}",
        }

        new_number = (
            request.POST.get("phone") if request.POST.get("phone") != "N/A" else None
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
            print("====updating profile image============")
            new_profile_image = request.FILES["profile_image"]
            url = f"{config('api_url')}/uploads/{role}/uploads/"
            files = {"file": new_profile_image}
            response = requests.put(url, files=files)
            if response.status_code == 200:
                print("====profile image updated============")
                messages.success(request, "Profile image updated successfully")
            else:
                messages.error(request, "Failed to update profile image")

        user = request.COOKIES.get(f"current_{role}")
        user_id = get_user_id(role, user)

        if new_number:
            update_phone_number(request, new_number, headers, user_id, role)
        if new_twitter:
            update_twitter_handle(request, new_twitter, headers, user_id, role)
        if new_facebook:
            update_facebook_handle(request, new_facebook, headers, user_id, role)
        if new_linkedin:
            update_linkedin_handle(request, new_linkedin, headers, user_id, role)

    return redirect(
        reverse(
            f"{role}:profile",
            args=[get_user_id(role, request.COOKIES.get(f"current_{role}"))],
        )
    )


def update_phone_number(request, new_phone_number, headers, user_id, role):
    if len(new_phone_number) == 9:
        new_phone_number = new_phone_number.replace(" ", "")
        url = f"{config('api_url')}/users/{role}/update_phone_number"
        data = {"phone_number": new_phone_number}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            messages.success(request, "Phone number updated successfully")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update phone number")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
    else:
        messages.error(request, "Phone number must be 9 digits")
        return redirect(reverse(f"{role}:profile", args=[user_id]))


# TODO: find a way to check if the twitter handle is valid
def update_twitter_handle(request, new_twitter_handle, headers, user_id, role):
    if len(new_twitter_handle) > 0:
        new_twitter_handle = new_twitter_handle.replace(" ", "")
        url = f"{config('api_url')}/users/{role}/update_twitter_handle"
        data = {"twitter": new_twitter_handle}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            messages.success(request, "Twitter handle updated successfully")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update twitter handle")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
    else:
        messages.error(request, "Twitter handle cannot be empty")
        return redirect(reverse(f"{role}:profile", args=[user_id]))


def update_facebook_handle(request, new_facebook_handle, headers, user_id, role):
    if len(new_facebook_handle) > 0:
        new_facebook_handle = new_facebook_handle.replace(" ", "")
        url = f"{config('api_url')}/users/{role}/update_facebook_handle"
        data = {"facebook": new_facebook_handle}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            messages.success(request, "Facebook handle updated successfully")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update facebook handle")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
    else:
        messages.error(request, "Facebook handle cannot be empty")
        return redirect(reverse(f"{role}:profile", args=[user_id]))


def update_linkedin_handle(request, new_linkedin_handle, headers, user_id, role):
    if len(new_linkedin_handle) > 0:
        new_linkedin_handle = (
            f"https://linkedin.com/in/{new_linkedin_handle}"
        ).replace(" ", "")
        url = f"{config('api_url')}/users/{role}/update_linkedin_handle"
        data = {"linkedin": new_linkedin_handle}
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            messages.success(request, "Linkedin handle updated successfully")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
        else:
            messages.error(request, "Failed to update linkedin handle")
            return redirect(reverse(f"{role}:profile", args=[user_id]))
    else:
        messages.error(request, "Linkedin handle cannot be empty")
        return redirect(reverse(f"{role}:profile", args=[user_id]))
