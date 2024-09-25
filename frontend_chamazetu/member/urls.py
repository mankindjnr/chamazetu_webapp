from django.urls import path

from . import views

app_name = "member"

urlpatterns = [
    path("dashboard", views.dashboard, name="dashboard"),
    path("profile/<int:member_id>", views.profile, name="profile"),
    path(
        "change_password/<int:user_id>", views.change_password, name="change_password"
    ),
    path(
        "access_chama/<str:chamaname>/<int:chama_id>",
        views.access_chama,
        name="access_chama",
    ),
    path(
        "activities/<str:chama_name>/<int:chama_id>/<str:activity_type>/<int:activity_id>",
        views.access_activity,
        name="activities",
    ),
    path("chama/<int:chamaid>", views.view_chama, name="chama"),
    path(
        "members_tracker/<str:chama_name>",
        views.members_tracker,
        name="members_tracker",
    ),
    path(
        "fines_tracker/<str:chama_name>/<str:role>",
        views.fines_tracker,
        name="fines_tracker",
    ),
    path(
        "view_activity_members/<str:activity_name>/<int:activity_id>",
        views.view_activity_members,
        name="view_activity_members",
    ),
    path(
        "view_chama_members/<str:chama_name>/<int:chama_id>",
        views.view_chama_members,
        name="view_chama_members",
    ),
    path(
        "chama_activities/<str:chama_name>/<int:chama_id>",
        views.chama_activities,
        name="chama_activities",
    ),
    path(
        "get_about_chama/<str:chama_name>/<int:chama_id>",
        views.get_about_chama,
        name="get_about_chama",
    ),
    path(
        "get_about_activity/<str:activity_name>/<int:activity_id>",
        views.get_about_activity,
        name="get_about_activity",
    ),
    path(
        "activate_auto_contributions/<str:activity_name>/<int:activity_id>",
        views.activate_auto_contributions,
        name="activate_auto_contributions",
    ),
    path(
        "deactivate_auto_contributions/<str:activity_name>/<int:activity_id>",
        views.deactivate_auto_contributions,
        name="deactivate_auto_contributions",
    ),
    path(
        "profile_updater",
        views.profile_updater,
        name="profile_updater",
    ),
    path("join", views.join_chama, name="join"),
    path(
        "join_activity/<str:chama_name>/<int:activity_id>",
        views.join_activity,
        name="join_activity",
    ),
    path(
        "from_wallet_to_activity/<str:chama_name>/<int:chama_id>/<str:activity_type>/<int:activity_id>",
        views.from_wallet_to_activity,
        name="from_wallet_to_activity",
    ),
    path(
        "from_wallet_to_select_activity/<int:chama_id>/<str:chama_name>",
        views.from_wallet_to_select_activity,
        name="from_wallet_to_select_activity",
    ),
    path("wallet_transactions", views.wallet_transactions, name="wallet_transactions"),
    path(
        "fix_mpesa_to_wallet_deposit",
        views.fix_mpesa_to_wallet_deposit,
        name="fix_mpesa_to_wallet_deposit",
    ),
]
