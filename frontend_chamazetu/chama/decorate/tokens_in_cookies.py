from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from functools import wraps
import asyncio

"""
This decorator checks if the access token is in the cookies

modify your tokens_in_cookies decorator to support async views. Here's how you can do it:
Check if the decorated function is a coroutine.
If it is, await the coroutine before returning the response.
"""


# refresh here and store the tokens as well
def tokens_in_cookies():
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            access_token = request.COOKIES.get("access_token")
            refresh_token = request.COOKIES.get("refresh_token")
            if not access_token or not refresh_token:
                return HttpResponseRedirect(reverse("chama:signin"))
            response = func(request, *args, **kwargs)
            return response

        return wrapper

    return decorator


def async_tokens_in_cookies():
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            access_token = request.COOKIES.get("access_token")
            refresh_token = request.COOKIES.get(f"refresh_token")
            if not access_token or not refresh_token:
                return HttpResponseRedirect(reverse("chama:signin"))
            response = await func(request, *args, **kwargs)
            return response

        return wrapper

    return decorator
