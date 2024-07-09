from functools import wraps
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse

from chama.usermanagement import validate_token, refresh_token, refresh_token_async


def validate_and_refresh_token(role):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            response = validate_token(request, role)
            if isinstance(response, HttpResponseRedirect):
                refreshed_response = refresh_token(request, role)
                if isinstance(refreshed_response, HttpResponseRedirect):
                    return refreshed_response
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def async_validate_and_refresh_token(role):
    def decorator(view_func):
        @wraps(view_func)
        async def _wrapped_view(request, *args, **kwargs):
            response = validate_token(request, role)
            if isinstance(response, HttpResponseRedirect):
                refreshed_response = await refresh_token_async(request, role)
                if isinstance(refreshed_response, HttpResponseRedirect):
                    return refreshed_response
            return await view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
