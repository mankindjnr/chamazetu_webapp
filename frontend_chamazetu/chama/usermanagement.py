import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseServerError, JsonResponse
from django.urls import reverse
from functools import wraps
from asgiref.sync import sync_to_async
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import aiohttp
from http import HTTPStatus

from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib import messages
from frontend_chamazetu import settings

from .tasks import sending_email

load_dotenv()


def validate_token(request):
    try:
        jwt.decode(
            request.COOKIES.get("access_token").split(" ")[1],
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"],
        )
        print("---------valid_token---------")
    except (InvalidTokenError, ExpiredSignatureError) as e:
        print("---------invalid_token---------")
        return redirect(reverse("chama:signin"))


def refresh_token(request):
    try:
        current_role = request.COOKIES.get("current_role")
        refresh_token = request.COOKIES.get("refresh_token").split(" ")[1]
        print("---------refreshing_token---------")
        decoded_token = jwt.decode(
            refresh_token, os.getenv("JWT_SECRET"), algorithms=["HS256"]
        )
        # If the refresh token is valid, generate a new access token
        email_claim = decoded_token.get("sub")
        data = {
            "username": email_claim,
        }

        headers = {"Content-type": "application/json"}
        refresh_access = requests.post(
            f"{os.getenv('api_url')}/auth/refresh",
            data=json.dumps(data),
            headers=headers,
        )
        refresh_data = refresh_access.json()
        new_access_token = refresh_data["new_access_token"]
        referer = request.META.get("HTTP_REFERER", f"{current_role}:dashboard")
        response = HttpResponseRedirect(referer)
        response.set_cookie(
            "access_token",
            f"Bearer {new_access_token}",
            secure=True,
            httponly=True,
            samesite="Strict",
        )
        return response
    except (InvalidTokenError, ExpiredSignatureError) as e:
        print("---------invalid_token---------")
        return HttpResponseRedirect(reverse("chama:signin"))
    except Exception as e:
        return HttpResponseRedirect(reverse("chama:signin"))


async def refresh_token_async(request):
    try:
        current_role = request.COOKIES.get("current_role")
        refresh_token = request.COOKIES.get("refresh_token").split(" ")[1]
        print("---------refreshing_token---------")
        decoded_token = jwt.decode(
            refresh_token, os.getenv("JWT_SECRET"), algorithms=["HS256"]
        )
        # If the refresh token is valid, generate a new access token
        email_claim = decoded_token.get("sub")
        data = {
            "username": email_claim,
        }

        headers = {"Content-type": "application/json"}
        refresh_access = await sync_to_async(requests.post)(
            f"{os.getenv('api_url')}/auth/refresh",
            data=json.dumps(data),
            headers=headers,
        )
        refresh_data = refresh_access.json()
        new_access_token = refresh_data["new_access_token"]
        referer = request.META.get("HTTP_REFERER", f"{current_role}:dashboard")
        response = HttpResponseRedirect(referer)
        response.set_cookie(
            "access_token",
            f"Bearer {new_access_token}",
            secure=True,
            httponly=True,
            samesite="Strict",
        )
        return response
    except (InvalidTokenError, ExpiredSignatureError) as e:
        print("---------invalid_token---------")
        return HttpResponseRedirect(reverse("chama:signin"))
    except Exception as e:
        return HttpResponseRedirect(reverse("chama:signin"))


def get_user_email(id):
    url = f"{os.getenv('api_url')}/users/email/{id}"
    resp = requests.get(url)
    if resp.status_code == HTTPStatus.OK:
        user = resp.json()
        email = user["email"]
        return email
    return None


def signin(request):
    if request.method == "POST":
        data = {
            "username": request.POST.get("email").strip().lower(),
            "password": request.POST["password"],
        }

        # TODO: check if the user is already logged in and redirect to the dashboard or # remember me
        # TODO: if the user email is not the same as the payload of the token, signout the other user in the background
        response = requests.post(f"{os.getenv('api_url')}/auth/login/", data=data)

        if response.status_code == HTTPStatus.OK:
            access_tokens = {}
            refresh_tokens = {}
            access_tokens["access_token"] = response.json()["access_token"]
            refresh_tokens["refresh_token"] = response.json()["refresh_token"]
            current_user = request.POST["email"].strip().lower()

            # default role is member, if the user has not joined any chama, check if they have created any chama
            # if they have created but not a member, redirect to manager dashboard, else redirect to member dashboard
            headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {access_tokens.get('access_token')}",
            }

            role = "member"
            post_login_redirect = request.session.get("post_login_redirect")
            response = None
            if post_login_redirect:
                response = redirect(post_login_redirect)
                del request.session["post_login_redirect"]  # remove the session key
            else:
                initial_role = requests.get(
                    f"{os.getenv('api_url')}/users/active_role/{current_user}",
                )
                if initial_role.status_code == HTTPStatus.OK:
                    role = initial_role.json()["active_role"]
                response = redirect(reverse(f"{role}:dashboard"))

            # successful login - store tokens - redirect to dashboard
            response.set_cookie(
                "current_user",
                current_user,
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            response.set_cookie(
                "current_role",
                role,
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            response.set_cookie(
                f"access_token",
                f"Bearer {access_tokens.get('access_token')}",
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            response.set_cookie(
                f"refresh_token",
                f"Bearer {refresh_tokens.get('refresh_token')}",
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            return response
        else:
            # unsuccessful login - redirect to login page - send message to user - not verified
            messages.error(request, f"email/password incorrect, please try again")
            return render(request, f"chama/signin.html")
    else:
        return render(request, f"chama/signin.html")

    page = f"chama/signin.html"
    return render(request, page)


def switch_to(request, role):
    response = HttpResponseRedirect(reverse(f"{role}:dashboard"))
    response.set_cookie("current_role", role)
    return response


def signup(request):
    if request.method == "POST":
        first_name = request.POST["first_name"]
        last_name = request.POST["last_name"]
        email = request.POST.get("email", "").strip().lower()
        password = request.POST["password"]
        confirm_password = request.POST["password2"]

        if password != confirm_password:
            messages.error(request, "passwords do not match")
            return render(request, f"chama/signup.html")

        data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
            "is_active": False,
            "email_verified": False,
        }

        headers = {"Content-type": "application/json"}
        response = requests.post(
            f"{os.getenv('api_url')}/users",
            data=json.dumps(data),
            headers=headers,
        )

        if response.status_code == HTTPStatus.CREATED:
            # successful signup - redirect to login page
            current_user = response.json()["User"][0]
            # -------------------email verification-------------------------------------
            current_site = get_current_site(request)
            mail_subject = "Activate your chamaZetu account."
            message = render_to_string(
                "chama/activateAccount.html",
                {
                    "user": email,
                    "current_site": current_site,
                    "uid": urlsafe_base64_encode(force_bytes(current_user["id"])),
                    "token": current_user["activation_code"],
                },
            )

            from_email = settings.EMAIL_HOST_USER
            to_email = [current_user["email"]]

            sending_email.delay(mail_subject, message, from_email, to_email)

            messages.success(
                request,
                "Account created successfully. Please check your email to activate your account.",
            )
            #  -------------------email confirmation-------------------------------------
            return HttpResponseRedirect(reverse("chama:signin"))
        else:
            messages.error(request, "email already in use as manager/member")
            return HttpResponseRedirect(reverse("chama:signup"))

    page = f"chama/signup.html"
    return render(request, page)


def signout(request):
    # TODO: in the server side, invalidate the token. create table for tokens blcklist/whitelist/delete
    response = HttpResponseRedirect(reverse("chama:index"))
    response.delete_cookie(f"current_role")
    response.delete_cookie(f"current_user")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


# validation of the signup jwt token (15 min lifespan)
def verify_signup_token(request, token):
    try:
        jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return True
    except InvalidTokenError as e:
        return HttpResponseRedirect(reverse("chama:signin"))


def check_token_validity(token):
    try:
        jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return True
    except InvalidTokenError as e:
        return HttpResponseRedirect(reverse("chama:signin"))


# the activation link sent to the user's email
def activate(request, uidb64, token):
    uid = force_str(urlsafe_base64_decode(uidb64))  # decode the uidb64 to user id
    user = get_user_email(uid)

    if verify_signup_token(request, token):
        # activate user and redirect to home page

        print("---------activating_user---------")
        email_verified_resp = requests.put(
            f"{os.getenv('api_url')}/users/email_verification/{uid}",
            json={"user_email": user},
        )

        if email_verified_resp.status_code == HTTPStatus.OK:
            messages.success(
                request, "Account activated successfully. You can now login."
            )
            return HttpResponseRedirect(reverse("chama:signin"))
        else:
            messages.error(request, "Account activation failed")
            return HttpResponseRedirect(reverse("chama:signin"))
    else:
        # TODO: if the token has expired, send another one - checking if the user is thne database and unverified
        messages.error(request, "Activation link has expired!")
        return HttpResponseRedirect(reverse("chama:signin"))


# changing password while logged out
def forgot_password(request):
    if request.method == "POST":
        email = (request.POST["email"]).strip()

        user_resp = requests.get(f"{os.getenv('api_url')}/users/{email}")
        if user_resp.status_code == HTTPStatus.OK:
            # TODO: call backend url to create an activation token and send email i;e signup
            return render(
                request,
                "chama/update_forgotten_passwords.html",
                {"user": user_resp.json()["email"]},
            )
        else:
            messages.error(request, "User not found")
            return HttpResponseRedirect(reverse("chama:forgot_password"))

    return render(request, "chama/forgot_password_form.html")


def update_forgotten_password(request):
    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]
        confirm_password = request.POST["password2"]

        if password != confirm_password:
            messages.error(request, "passwords do not match")
            return HttpResponseRedirect(reverse("chama:update_forgotten_password"))

        data = {"email": email, "updated_password": password}
        updated_resp = requests.put(
            f"{os.getenv('api_url')}/users/update_password", json=data
        )
        if updated_resp.status_code == HTTPStatus.OK:
            messages.success(request, "password has been successfully updated")
            return HttpResponseRedirect(reverse("chama:signin"))
        else:
            messages.error(request, "password update failed")
            return HttpResponseRedirect(reverse("chama:forgot_password"))

    # might have to get a update forgotten password page
    return render(request, "chama/forgot_password_form.html")


def join_newsletter(request):
    if request.method == "POST":
        email = request.POST["email"]
        data = {"email": email}
        response = requests.post(
            f"{os.getenv('api_url')}/newsletter/subscribe", json=data
        )
        if response.status_code == HTTPStatus.CREATED:
            print("---------newsletter_success---------")
            mail_subject = "chamaZetu Newsletter Subscription."
            message = render_to_string(
                "chama/newsletterConfirmation.html",
                {
                    "user": response.json()["email"],
                    "date_subscribed": response.json()["date_subscribed"],
                },
            )

            from_email = settings.EMAIL_HOST_USER
            to_email = [response.json()["email"]]

            sending_email.delay(mail_subject, message, from_email, to_email)

            print(response.json())
            messages.success(request, "You have successfully joined our newsletter")
        else:
            messages.error(request, "Failed to join newsletter")

    return HttpResponseRedirect(reverse("chama:index"))
