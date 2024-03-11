from django.urls import path

from . import views

app_name = "manager"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile", views.profile, name="profile"),
]
