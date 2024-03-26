from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse

"""
This decorator checks if the access token is in the cookies
"""


# refresh here and store the tokens as well
def tokens_in_cookies(role):
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            access_token = request.COOKIES.get(f"{role}_access_token")
            refresh_token = request.COOKIES.get(f"{role}_refresh_token")
            if not access_token or not refresh_token:
                return HttpResponseRedirect(reverse("chama:signin", args=[role]))
            response = func(request, *args, **kwargs)
            return response

        return wrapper

    return decorator
