from django.urls import path

from . import views

app_name = "chama"

urlpatterns = [
    path("", views.index, name="index"),
    path("signin/<str:role>", views.signin, name="signin"),
    path("signup/<str:role>", views.signup, name="signup"),
    path("signout/<str:role>", views.signout, name="signout"),
    path("activate/<role>/<uidb64>/<token>", views.activate, name="activate"),
    path("forgot_password/<str:role>", views.forgot_password, name="forgot_password"),
    path(
        "update_forgotten_password/<str:role>",
        views.update_forgotten_password,
        name="update_forgotten_password",
    ),
    path("chamas", views.get_all_chamas, name="chamas"),
    path("chamas/<str:role>", views.get_all_chamas, name="chamas"),
    path("chama/<int:chamaid>", views.get_chama, name="chama"),
    path("callback", views.call_back, name="callback"),
    path(
        "TransactionStatus/result",
        views.status_result_receiver,
        name="transactionstatus",
    ),
    path(
        "TransactionStatus/queue",
        views.status_timeout_receiver,
        name="transactiontimeout",
    ),
    path(
        "callback/registration",
        views.registration_call_back,
        name="registration_callback",
    ),
    path("join_newsletter", views.join_newsletter, name="join_newsletter"),
]
