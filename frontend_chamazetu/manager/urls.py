from django.urls import path

from . import views

app_name = "manager"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile", views.profile, name="profile"),
    path("create_chama", views.create_chama, name="create_chama"),
    path("chama/<str:key>", views.chama, name="chama"),
    path("join_status", views.chama_join_status, name="join_status"),
]
