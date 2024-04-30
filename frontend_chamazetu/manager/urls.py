from django.urls import path

from . import views

app_name = "manager"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile/<int:manager_id>", views.profile, name="profile"),
    path(
        "change_password/<int:manager_id>",
        views.change_password,
        name="change_password",
    ),
    path("create_chama", views.create_chama, name="create_chama"),
    path("chama/<str:key>", views.chama, name="chama"),
    path(
        "view_chama_members/<str:chama_name>",
        views.view_chama_members,
        name="view_chama_members",
    ),
    path(
        "members_tracker/<str:chama_name>",
        views.members_tracker,
        name="members_tracker",
    ),
    path("join_status", views.chama_join_status, name="join_status"),
    path(
        "activate_deactivate_chama",
        views.activate_deactivate_chama,
        name="activate_deactivate_chama",
    ),
    path("invest", views.invest, name="invest"),
    path(
        "withdraw_investment",
        views.withdraw_from_investment,
        name="withdraw_investment",
    ),
]
