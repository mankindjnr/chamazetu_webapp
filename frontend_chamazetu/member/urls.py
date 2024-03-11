from django.urls import path

from . import views

app_name = "member"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile", views.profile, name="profile"),
]
