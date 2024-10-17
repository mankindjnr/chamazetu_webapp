from django.http import HttpResponse, JsonResponse
from .textbelt_sms import send_sms


def send_sms_view(request):
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        message = "Hello, this is a test message from the Django server. If you received this message, it means the server is working correctly."

        response = send_sms(phone_number, message)

        return JsonResponse(response)
    else:
        return HttpResponse("Invalid request method")
