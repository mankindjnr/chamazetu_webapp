import requests, jwt, json, os
from dotenv import load_dotenv
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib import messages
from frontend_chamazetu import settings

from .tasks import sending_email

load_dotenv()


def validate_token(request, role=None):
    try:
        print("---------validating_token---------")
        print(request.COOKIES.get(f"{role}_access_token"))
        jwt.decode(
            request.COOKIES.get(f"{role}_access_token").split(" ")[1],
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"],
        )
        print("---------valid_token---------")
    except (InvalidTokenError, ExpiredSignatureError) as e:
        print("---------invalid_token---------")
        return redirect(reverse("chama:signin", args=[role]))


def refresh_token(request, role):
    print("---------refresh_token-PATH--------")
    print(request.path)  # /manager/chama/vuka
    try:
        refresh_token = request.COOKIES.get(f"{role}_refresh_token").split(" ")[1]
        print("---------refreshing_token---------")
        decoded_token = jwt.decode(
            refresh_token, os.getenv("JWT_SECRET"), algorithms=["HS256"]
        )
        # If the refresh token is valid, generate a new access token
        email_claim = decoded_token.get("sub")
        data = {
            "username": email_claim,
            "role": role,
        }

        headers = {"Content-type": "application/json"}
        refresh_access = requests.post(
            f"{os.getenv('api_url')}/auth/refresh",
            data=json.dumps(data),
            headers=headers,
        )
        refresh_data = refresh_access.json()
        new_access_token = refresh_data["new_access_token"]
        # response = HttpResponseRedirect(reverse(f"{role}:dashboard"))
        response = HttpResponseRedirect(request.path)
        response.set_cookie(
            f"{role}_access_token",
            f"Bearer {new_access_token}",
            secure=True,
            httponly=True,
            samesite="Strict",
        )
        return response
    except (InvalidTokenError, ExpiredSignatureError) as e:
        print("---------invalid_token---------")
        return HttpResponseRedirect(reverse("chama:signin", args=[role]))
    except Exception as e:
        print("---------error---------")
        return HttpResponseRedirect(reverse("chama:signin", args=[role]))


def get_user_email(role, id):
    url = f"{os.getenv('api_url')}/users/email/{role}/{id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        user = resp.json()
        email = user["email"]
        return email
    return None


def signin(request, role):
    if request.method == "POST":
        data = {
            "username": request.POST["email"],
            "password": request.POST["password"],
        }

        # TODO: check if the user is already logged in and redirect to the dashboard or # remember me
        # TODO: if the user email is not the same as the payload of the token, signout the other user in the background
        # print("---------signin---path------")
        # if request.path == "/signin/manager":
        #     if request.COOKIES.get("manager_access_token"):
        #         if
        # TODO: include a try and retry mechanism for the auth route call
        # send the data to the auth server for verification and login
        response = requests.post(
            f"{os.getenv('api_url')}/auth/{role}s/login/", data=data
        )

        if response.status_code == 200:
            access_tokens = {}
            refresh_tokens = {}
            access_tokens[role] = response.json()["access_token"]
            refresh_tokens[role] = response.json()["refresh_token"]
            current_user = request.POST["email"]

            # check if user is a member or manager
            if role == "manager":
                response = redirect(reverse("manager:dashboard"))
            elif role == "member":
                response = redirect(reverse("member:dashboard"))

            # successful login - store tokens - redirect to dashboard
            response.set_cookie(
                f"current_{role}",
                current_user,
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            response.set_cookie(
                f"{role}_access_token",
                f"Bearer {access_tokens.get(role)}",
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            response.set_cookie(
                f"{role}_refresh_token",
                f"Bearer {refresh_tokens.get(role)}",
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            return response
        else:
            # unsuccessful login - redirect to login page - send message to user - not verified
            messages.error(request, f"user not a {role} or email not verified")
            return render(request, f"chama/{role}login.html")
    else:
        return render(request, f"chama/{role}login.html")

    page = f"chama/{role}login.html"
    return render(request, page)


def signup(request, role):
    if request.method == "POST":
        first_name = request.POST["first_name"]
        last_name = request.POST["last_name"]
        email = request.POST["email"]
        password = request.POST["password"]
        confirm_password = request.POST["password2"]

        if password != confirm_password:
            messages.error(request, "passwords do not match")
            return render(request, f"chama/{role}signup.html")

        data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
            "is_active": False,
            "email_verified": False,
            "role": role,
        }

        headers = {"Content-type": "application/json"}
        response = requests.post(
            f"{os.getenv('api_url')}/users",
            data=json.dumps(data),
            headers=headers,
        )

        if response.status_code == 201:
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
                    "role": role,
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
            role = role
            return HttpResponseRedirect(reverse("chama:signin", args=[role]))
        else:
            messages.error(request, "email already in use as manager/member")
            return HttpResponseRedirect(reverse("chama:signup", args=[role]))

    page = f"chama/{role}signup.html"
    return render(request, page)


def signout(request, role):
    # TODO: in the server side, invalidate the token. create table for tokens blcklist/whitelist/delete
    response = HttpResponseRedirect(reverse("chama:index"))
    response.delete_cookie(f"current_{role}")
    response.delete_cookie(f"{role}_access_token")
    response.delete_cookie(f"{role}_refresh_token")
    return response


# validation of the signup jwt token (15 min lifespan)
def verify_signup_token(request, token, role):
    try:
        jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return True
    except InvalidTokenError as e:
        return HttpResponseRedirect(reverse("chama:signin", args=[role]))


# the activation link sent to the user's email
def activate(request, role, uidb64, token):
    uid = force_str(urlsafe_base64_decode(uidb64))  # decode the uidb64 to user id
    user = get_user_email(role, uid)

    if user is not None and verify_signup_token(
        request, token, role
    ):  # validate the jwt token here
        # activate user and redirect to home page

        print("---------activating_user---------")
        print(uid)
        email_verified_resp = None
        if role == "manager":
            print("---------activating_manager---------")
            email_verified_resp = requests.put(
                f"{os.getenv('api_url')}/users/manager_email_verification/{uid}",
                json={"user_email": user},
            )
        elif role == "member":
            print("---------activating_member---------")
            email_verified_resp = requests.put(
                f"{os.getenv('api_url')}/users/member_email_verification/{uid}",
                json={"user_email": user},
            )

        if email_verified_resp.status_code == 200:
            messages.success(
                request, "Account activated successfully. You can now login."
            )
            return HttpResponseRedirect(reverse("chama:signin", args=[role]))
        else:
            messages.error(request, "Account activation failed")
            return HttpResponseRedirect(reverse("chama:signin", args=[role]))
    else:
        # TODO: if the token has expired, send another one - checking if the user is thne database and unverified
        messages.error(request, "Activation link has expired!")
        return HttpResponseRedirect(reverse("chama:signin", args=[role]))


# changing password while logged out
def forgot_password(request, role):
    if request.method == "POST":
        email = (request.POST["email"]).strip()

        user_resp = requests.get(f"{os.getenv('api_url')}/users/{role}/{email}")
        if user_resp.status_code == 200:
            # TODO: call backend url to create an activation token and send email i;e signup
            return render(
                request,
                "chama/update_forgotten_passwords.html",
                {"role": role, "user": user_resp.json()["email"]},
            )
        else:
            messages.error(request, "User not found")
            return HttpResponseRedirect(reverse("chama:forgot_password", args=[role]))

    return render(request, "chama/forgot_password_form.html", {"role": role})


def update_forgotten_password(request, role):
    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]
        confirm_password = request.POST["password2"]

        if password != confirm_password:
            messages.error(request, "passwords do not match")
            return HttpResponseRedirect(
                reverse("chama:update_forgotten_password", args=[role])
            )

        data = {"email": email, "updated_password": password}
        updated_resp = requests.put(
            f"{os.getenv('api_url')}/users/{role}/update_password", json=data
        )
        if updated_resp.status_code == 200:
            messages.success(request, "password has been successfully updated")
            return HttpResponseRedirect(reverse("chama:signin", args=[role]))
        else:
            messages.error(request, "password update failed")
            return HttpResponseRedirect(reverse("chama:forgot_password", args=[role]))

    # might have to get a update forgotten password page
    return render(request, "chama/forgot_password_form.html")
