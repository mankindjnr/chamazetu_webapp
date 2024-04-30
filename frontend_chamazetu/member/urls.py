from django.urls import path

from . import views

app_name = "member"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile/<int:member_id>", views.profile, name="profile"),
    path(
        "change_password/<int:user_id>", views.change_password, name="change_password"
    ),
    path("access_chama/<str:chamaname>", views.access_chama, name="access_chama"),
    path("chama/<int:chamaid>", views.view_chama, name="chama"),
    path(
        "members_tracker/<str:chama_name>",
        views.members_tracker,
        name="members_tracker",
    ),
    path(
        "view_chama_members/<str:chama_name>",
        views.view_chama_members,
        name="view_chama_members",
    ),
    path("profile_updater/<str:role>", views.profile_updater, name="profile_updater"),
    path("join", views.join_chama, name="join"),
    path(
        "direct_deposit_to_chama",
        views.direct_deposit_to_chama,
        name="direct_deposit_to_chama",
    ),
    path(
        "from_wallet_to_chama", views.from_wallet_to_chama, name="from_wallet_to_chama"
    ),
    path("deposit_to_wallet", views.deposit_to_wallet, name="deposit_to_wallet"),
    path(
        "withdraw_from_wallet", views.withdraw_from_wallet, name="withdraw_from_wallet"
    ),
]
