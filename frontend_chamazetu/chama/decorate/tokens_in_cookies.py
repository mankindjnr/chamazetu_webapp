from django.http import HttpResponseRedirect
from django.urls import reverse

"""
This decorator checks if the access token is in the cookies
"""


# refresh here and store the tokens as well
def tokens_in_cookies(role):
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if not request.COOKIES.get("access_token") or not request.COOKIES.get(
                "refresh_token"
            ):
                return HttpResponseRedirect(reverse("signin", args=[role]))

            return func(request, *args, **kwargs)

        return wrapper

    return decorator
