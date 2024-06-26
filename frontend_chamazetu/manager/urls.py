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
        "get_about_chama/<str:chama_name>",
        views.get_about_chama,
        name="get_about_chama",
    ),
    path(
        "update_chama_description/<str:chama_name>",
        views.update_chama_description,
        name="update_chama_description",
    ),
    path(
        "update_chama_mission/<str:chama_name>",
        views.update_chama_mission,
        name="update_chama_mission",
    ),
    path(
        "update_chama_vision/<str:chama_name>",
        views.update_chama_vision,
        name="update_chama_vision",
    ),
    path(
        "add_chama_faqs/<str:chama_name>", views.add_chama_faqs, name="add_chama_faqs"
    ),
    path(
        "add_chama_rules/<str:chama_name>",
        views.add_chama_rules,
        name="add_chama_rules",
    ),
    path(
        "delete_chama_rule/<str:chama_name>/<int:rule_id>",
        views.delete_chama_rule,
        name="delete_chama_rule",
    ),
    path(
        "delete_chama_faq/<str:chama_name>/<int:faq_id>",
        views.delete_chama_faq,
        name="delete_chama_faq",
    ),
    path(
        "members_tracker/<str:chama_name>",
        views.members_tracker,
        name="members_tracker",
    ),
    path(
        "new_members/<int:chama_id>/<str:status>", views.new_members, name="new_members"
    ),
    path(
        "activate_chama",
        views.activate_chama,
        name="activate_chama",
    ),
    path(
        "deactivate_chama",
        views.deactivate_chama,
        name="deactivate_chama",
    ),
    path("delete_chama/<int:chama_id>", views.delete_chama_by_id, name="delete_chama"),
    path("invest", views.invest, name="invest"),
    path(
        "withdraw_investment",
        views.withdraw_from_investment,
        name="withdraw_investment",
    ),
]
