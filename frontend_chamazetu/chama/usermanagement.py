import requests, jwt, json
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from decouple import config

from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib import messages
from frontend_chamazetu import settings

from .rawsql import execute_sql
from .tasks import sending_email


def validate_token(request, role=None):
    try:
        print("---------validating_token---------")
        print(request.COOKIES.get("access_token"))
        jwt.decode(
            request.COOKIES.get("access_token").split(" ")[1],
            config("JWT_SECRET"),
            algorithms=["HS256"],
        )
        print("---------valid_token---------")
    except (InvalidTokenError, ExpiredSignatureError) as e:
        print("---------invalid_token---------")
        return redirect(reverse("chama:signin", args=[role]))


def refresh_token(request, role):
    try:
        refresh_token = request.COOKIES.get("refresh_token").split(" ")[1]
        print("---------refreshing_token---------")
        decoded_token = jwt.decode(
            refresh_token, config("JWT_SECRET"), algorithms=["HS256"]
        )
        # If the refresh token is valid, generate a new access token
        email_claim = decoded_token.get("sub")
        data = {
            "username": email_claim,
        }

        headers = {"Content-type": "application/json"}
        refresh_access = requests.post(
            "http://chamazetu_backend:9400/auth/refresh",
            data=json.dumps(data),
            headers=headers,
        )
        refresh_data = refresh_access.json()
        new_access_token = refresh_data["new_access_token"]
        response = HttpResponseRedirect(reverse(f"{role}:dashboard"))
        response.set_cookie(
            "access_token",
            f"Bearer {new_access_token}",
            secure=True,
            httponly=True,
            samesite="Strict",
        )
        return response
    except (InvalidTokenError, ExpiredSignatureError) as e:
        return HttpResponseRedirect(reverse("chama:signin", args=[role]))


def signin(request, role):
    if request.method == "POST":
        data = {
            "username": request.POST["email"],
            "password": request.POST["password"],
        }
        # TODO: include a try and retry mechanism for the auth route call
        # send the data to the auth server for verification and login
        response = requests.post(
            f"http://chamazetu_backend:9400/auth/{role}s/login/", data=data
        )

        if response.status_code == 200:
            access_token = response.json()["access_token"]
            refresh_token = response.json()["refresh_token"]
            current_user = request.POST["email"]

            # check if user is a member or manager
            if role == "manager":
                response = redirect(reverse("manager:dashboard"))
            elif role == "member":
                response = redirect(reverse("member:dashboard"))

            # successful login - store tokens - redirect to dashboard
            response.set_cookie(
                "current_user",
                current_user,
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            response.set_cookie(
                "access_token",
                f"Bearer {access_token}",
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            response.set_cookie(
                "refresh_token",
                f"Bearer {refresh_token}",
                secure=True,
                httponly=True,
                samesite="Strict",
            )
            return response
    else:
        # unsuccessful login - redirect to login page - send message to user - not verified
        return render(request, f"chama/{role}login.html")

    page = f"chama/{role}login.html"
    return render(request, page)


def signup(request, role):  # implement the manager signup
    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]
        confirm_password = request.POST["password2"]

        if password != confirm_password:
            return render(request, f"chama/{role}signup.html")

        print("---------signup role---------")
        print(role)
        data = {
            "email": email,
            "password": password,
            "is_active": False,
            "email_verified": False,
            "role": role,
        }
        headers = {"Content-type": "application/json"}
        response = requests.post(
            "http://chamazetu_backend:9400/users",
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

    page = f"chama/{role}signup.html"
    return render(request, page)


def signout(request):
    # TODO: in the server side, invalidate the token
    response = HttpResponseRedirect(reverse("index"))
    response.delete_cookie("current_user")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


# validation of the signup jwt token (15 min lifespan)
def verify_signup_token(request, token, role):
    try:
        jwt.decode(token, config("JWT_SECRET"), algorithms=["HS256"])
        return True
    except InvalidTokenError as e:
        return HttpResponseRedirect(reverse("chama:signin", args=[role]))


# the activation link sent to the user's email
def activate(request, role, uidb64, token):
    print("---------activate---------")
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))  # decode the uidb64 to user id

        query = f"SELECT email FROM {role}s WHERE id = %s"
        params = [uid]
        user = execute_sql(query, params)
        print("---------raw user---------")
        print(user)

        user = user[0][0]
        print("---------user---------")
    except (TypeError, ValueError, OverflowError, SyntaxError, Exception) as e:
        print("---------error---------")
        print(e)
        user = None

    if user is not None and verify_signup_token(
        request, token, role
    ):  # validate the jwt token here
        # activate user and redirect to home page

        query = f"UPDATE {role}s SET email_verified = True, is_active = True WHERE id = %s RETURNING *"
        params = [uid]
        execute_sql(query, params)

        messages.success(request, "Account activated successfully. You can now login.")
        return HttpResponseRedirect(reverse("chama:signin", args=[role]))
    else:
        # if the token has expired, send another one - checking if the user is thne database and unverified
        return HttpResponse("Activation link is has expired!")
