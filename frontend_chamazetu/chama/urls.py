from django.urls import path

from . import views

app_name = "chama"

urlpatterns = [
    path("", views.index, name="index"),
    path("signin", views.signin, name="signin"),
    path("switch_to/<str:role>", views.switch_to, name="switch_to"),
    path("signup", views.signup, name="signup"),
    path("signout", views.signout, name="signout"),
    path("activate/<uidb64>/<token>", views.activate, name="activate"),
    path("forgot_password", views.forgot_password, name="forgot_password"),
    path(
        "update_forgotten_password",
        views.update_forgotten_password,
        name="update_forgotten_password",
    ),
    path("chamas", views.get_all_chamas, name="chamas"),
    path("chamas", views.get_all_chamas, name="chamas"),
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
    path("how_to_videos", views.how_to_videos, name="how_to_videos"),
    path("terms_of_service", views.terms_of_service, name="terms_of_service"),
    path("privacy_policy", views.privacy_policy, name="privacy_policy"),
]
