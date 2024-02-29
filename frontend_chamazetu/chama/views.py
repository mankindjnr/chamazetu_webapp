import requests, jwt, json
from django.shortcuts import render
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


# Create your views here.
def index(request):
    return render(request, "chama/index.html")


def validate_token(request, role=None):
    try:
        print("---------validate_token---------")
        print(request.COOKIES.get("access_token"))
        jwt.decode(
            request.COOKIES.get("access_token").split(" ")[1],
            config("JWT_SECRET"),
            algorithms=["HS256"],
        )
        print("---------valid_token---------")
    except (InvalidTokenError, ExpiredSignatureError) as e:
        return HttpResponseRedirect(reverse("signin", args=[role]))


def refresh_token(request, role):
    try:
        refresh_token = request.COOKIES.get("refresh_token").split(" ")[1]
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
            "http://chamazetu_backend:9400/users/refresh",
            data=json.dumps(data),
            headers=headers,
        )
        refresh_data = refresh_access.json()
        new_access_token = refresh_data["new_access_token"]
        response = HttpResponse("Access token refreshed")
        response.set_cookie("access_token", new_access_token)
        return response
    except (InvalidTokenError, ExpiredSignatureError) as e:
        return HttpResponseRedirect(reverse("signin", args=[role]))


def memberdashboard(request):
    access_token = request.COOKIES.get("access_token")

    # backend validation of token
    current_user = request.COOKIES.get("current_user")
    response = validate_token(request, "member")
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, "member")
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    return render(request, "chama/memberdashboard.html", {"current_user": current_user})


def managerdashboard(request):
    access_token = request.COOKIES.get("access_token")

    # might have to add a check for admin/ authorization - add it to the token
    # backend validation of token
    current_user = request.COOKIES.get("current_user")
    response = validate_token(request, "manager")
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, "manager")
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    return render(
        request, "chama/managerdashboard.html", {"current_user": current_user}
    )


def profile(request, role):
    response = validate_token(request, role)
    if isinstance(response, HttpResponseRedirect):
        refreshed_response = refresh_token(request, role)
        if isinstance(refreshed_response, HttpResponseRedirect):
            return refreshed_response

    page = f"chama/{role}profile.html"
    return render(request, page)


def signin(request, role):
    if request.method == "POST":
        data = {
            "username": request.POST["email"],
            "password": request.POST["password"],
        }

        # TODO: include a try and retry mechanism for the auth route call
        # send the data to the auth server for verification and login
        response = requests.post("http://chamazetu_backend:9400/users/login", data=data)
        print(response.json())

        if response.status_code == 200:
            access_token = response.json()["access_token"]
            refresh_token = response.json()["refresh_token"]
            current_user = request.POST["email"]

            # check if user is a member or manager from db
            query = "SELECT is_manager FROM users WHERE email = %s"
            params = [current_user]
            position = execute_sql(query, params)

            is_manager = position[0][0]
            if is_manager == True:
                response = HttpResponseRedirect(reverse("managerdashboard"))
            else:
                response = HttpResponseRedirect(reverse("memberdashboard"))

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
        username = request.POST["username"]
        password = request.POST["password"]
        confirm_password = request.POST["password2"]

        if password != confirm_password:
            return render(request, f"chama/{role}signup.html")

        # checking if the user is a manager or member
        is_manager = False
        is_member = False
        if role == "manager":
            is_manager = True
        elif role == "member":
            is_member = True

        # TODO: is_active to be changed to false by default till the user verifies their email
        data = {
            "email": email,
            "password": password,
            "username": username,
            "is_active": True,
            "is_manager": is_manager,
            "is_member": is_member,
            "is_staff": False,
            "is_verified": False,
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
            print("---------current_site---------")
            print(current_site)
            print()
            mail_subject = "Activate your chamaZetu account."
            message = render_to_string(
                "chama/activateAccount.html",
                {
                    "user": username,
                    "domain": current_site.domain,
                    "uid": urlsafe_base64_encode(force_bytes(current_user["id"])),
                    "token": current_user["activation_code"],
                },
            )

            from_email = settings.EMAIL_HOST_USER
            to_email = [current_user["email"]]

            verification_mail = EmailMultiAlternatives(
                subject=mail_subject, body=message, from_email=from_email, to=to_email
            )
            verification_mail.attach_alternative(message, "text/html")
            verification_mail.send(fail_silently=True)

            messages.success(
                request,
                "Account created successfully. Please check your email to activate your account.",
            )
            #  -------------------email confirmation-------------------------------------
            role = role
            return HttpResponseRedirect(reverse("signin", args=[role]))

    page = f"chama/{role}signup.html"
    return render(request, page)


# validation of the signup jwt token (15 min lifespan)
def verify_signup_token(request, token, role):
    try:
        jwt.decode(token, config("JWT_SECRET"), algorithms=["HS256"])
        return True
    except InvalidTokenError as e:
        return HttpResponseRedirect(reverse("signin", args=[role]))


# TODO: replace the supabase calls with the postgres calls - since the db is a container
# TODO: start using raw sql queries to interact with the db
# the activation link sent to the user's email
def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))  # decode the uid to user id
        # user = supabase.table("users").select("*").eq("id", uid).execute()

        query = "SELECT email, is_manager FROM users WHERE id = %s"
        params = [uid]
        user = execute_sql(query, params)
        print("---------raw user---------")
        print(user)
        print()

        role = user[0][1]
        if role == True:
            role = "manager"
        else:
            role = "member"

        user = user[0][0]

    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and verify_signup_token(
        request, token, role
    ):  # validate the jwt token here
        # activate user and redirect to home page
        # supabase.table("users").update({"is_verified": True}).eq("id", uid).execute()

        query = "UPDATE users SET is_verified = True WHERE id = %s RETURNING *"
        params = [uid]
        execute_sql(query, params)

        messages.success(request, "Account activated successfully. You can now login.")
        return HttpResponseRedirect(reverse("signin", args=[role]))
    else:
        # if the token has expired, send another one - checking if the user is thne database and unverified
        return HttpResponse("Activation link is invalid!")
