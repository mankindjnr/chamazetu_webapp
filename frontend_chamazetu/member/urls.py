from django.urls import path

from . import views

app_name = "member"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile", views.profile, name="profile"),
    path("chamas", views.my_chamas, name="chamas"),
    path("join", views.join_chama, name="join"),
]
