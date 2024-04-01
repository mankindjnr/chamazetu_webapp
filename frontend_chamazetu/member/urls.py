from django.urls import path

from . import views

app_name = "member"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile", views.profile, name="profile"),
    path("access_chama/<str:chamaname>", views.access_chama, name="access_chama"),
    path("chama/<int:chamaid>", views.view_chama, name="chama"),
    path("join", views.join_chama, name="join"),
    path("deposit", views.deposit_to_chama, name="deposit"),
]
