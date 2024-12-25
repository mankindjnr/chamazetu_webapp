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
    path(
        "create_activity/<int:chama_id>", views.create_activity, name="create_activity"
    ),
    path("chama/<str:key>", views.chama, name="chama"),
    path(
        "chama_activity/<int:activity_id>",
        views.chama_activity,
        name="chama_activity",
    ),
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
        "update_chama_description/<int:chama_id>/<str:chama_name>",
        views.update_chama_description,
        name="update_chama_description",
    ),
    path(
        "update_chama_mission/<int:chama_id>/<str:chama_name>",
        views.update_chama_mission,
        name="update_chama_mission",
    ),
    path(
        "update_chama_vision/<int:chama_id>/<str:chama_name>",
        views.update_chama_vision,
        name="update_chama_vision",
    ),
    path(
        "add_chama_faqs/<int:chama_id>/<str:chama_name>",
        views.add_chama_faqs,
        name="add_chama_faqs",
    ),
    path(
        "add_chama_rules/<int:chama_id>/<str:chama_name>",
        views.add_chama_rules,
        name="add_chama_rules",
    ),
    path(
        "delete_chama_rule/<int:chama_id>/<str:chama_name>/<int:rule_id>",
        views.delete_chama_rule,
        name="delete_chama_rule",
    ),
    path(
        "delete_chama_faq/<int:chama_id>/<str:chama_name>/<int:faq_id>",
        views.delete_chama_faq,
        name="delete_chama_faq",
    ),
    path(
        "members_tracker/<str:chama_name>",
        views.members_tracker,
        name="members_tracker",
    ),
    path(
        "accept_new_chama_members/<int:chama_id>",
        views.accept_new_chama_members,
        name="accept_new_chama_members",
    ),
    path(
        "activate_deactivate_chama/<int:chama_id>",
        views.activate_deactivate_chama,
        name="activate_deactivate_chama",
    ),
    path("delete_chama/<int:chama_id>", views.delete_chama_by_id, name="delete_chama"),
    path("invest", views.invest, name="invest"),
    path(
        "withdraw_investment",
        views.withdraw_from_investment,
        name="withdraw_investment",
    ),
    path(
        "new_activity_members/<str:activity_name>/<int:activity_id>",
        views.new_activity_members,
        name="new_activity_members",
    ),
    path(
        "deactivate_activate_activity/<str:activity_name>/<int:activity_id>",
        views.deactivate_activate_activity,
        name="deactivate_activate_activity",
    ),
    path(
        "restart_activity/<str:activity_name>/<int:activity_id>",
        views.restart_activity,
        name="restart_activity",
    ),
    path(
        "delete_activity/<int:activity_id>",
        views.delete_activity,
        name="delete_activity",
    ),
    path(
        "send_invite_to_members/<str:invite_to>/<str:name>/<int:id>",
        views.send_invite_to_members,
        name="send_invite_to_members",
    ),
    path(
        "invite_all/<str:invite_to>/<str:name>/<int:id>",
        views.send_activity_invite_to_all,
        name="invite_all",
    ),
    path(
        "rotating_order/<int:activity_id>",
        views.rotating_order,
        name="rotating_order",
    ),
    path(
        "create_random_rotation_order/<int:activity_id>",
        views.create_random_rotation_order,
        name="create_random_rotation_order",
    ),
    path(
        "disburse_funds/<int:activity_id>",
        views.disburse_funds,
        name="disburse_funds",
    ),
    path(
        "fines_tracker/<str:activity_name>/<int:activity_id>/<str:from_date>/<str:to_date>",
        views.fines_tracker,
        name="fines_tracker",
    ),
    path(
        "order_management/<int:activity_id>",
        views.order_management,
        name="order_management",
    ),
    path(
        "merry_go_round_share_increase/<int:activity_id>",
        views.merry_go_round_share_increase,
        name="merry_go_round_share_increase",
    ),
    path(
        "membership_management/<int:chama_id>",
        views.membership_management,
        name="membership_management",
    ),
    path(
        "allow_new_members/<int:chama_id>",
        views.allow_new_members,
        name="allow_new_members",
    ),
    path(
        "allow_new_activity_members/<int:activity_id>",
        views.allow_new_activity_members,
        name="allow_new_activity_members",
    ),
    path(
        "get_soft_loans/<int:activity_id>",
        views.get_soft_loans,
        name="get_soft_loans",
    ),
    path(
        "set_update_table_banking_interest_rate/<int:activity_id>",
        views.set_update_table_banking_interest_rate,
        name="set_update_table_banking_interest_rate",
    ),
    path(
        "get_loan_settings/<int:activity_id>",
        views.get_loan_settings,
        name="get_loan_settings",
    ),
    path(
        "update_loan_approval_settings/<int:activity_id>",
        views.update_loan_approval_settings,
        name="update_loan_approval_settings",
    ),
    path(
        "loan_eligibility/<int:activity_id>",
        views.loan_eligibility,
        name="loan_eligibility",
    ),
    path(
        "restrict_user/<int:activity_id>/<int:user_id>",
        views.restrict_user,
        name="restrict_user",
    ),
    path(
        "allow_user/<int:activity_id>/<int:user_id>",
        views.allow_user,
        name="allow_user",
    ),
    path(
        "approve_loan/<int:activity_id>/<int:loan_id>",
        views.approve_loan,
        name="approve_loan",
    ),
    path(
        "decline_loan/<int:activity_id>/<int:loan_id>",
        views.decline_loan,
        name="decline_loan",
    ),
    path(
        "disburse_dividends/<int:activity_id>",
        views.disburse_dividends,
        name="disburse_dividends",
    ),
    path(
        "dividend_disbursement/<int:activity_id>",
        views.dividend_disbursement,
        name="dividend_disbursement",
    ),
    path(
        "investment_marketplace/<int:chama_id>",
        views.investment_marketplace,
        name="investment_marketplace",
    ),
    path(
        "set_last_contribution_date/<int:activity_id>",
        views.set_last_contribution_date,
        name="set_last_contribution_date",
    ),
    path(
        "transfer_fines/<int:activity_id>",
        views.transfer_fines,
        name="transfer_fines",
    ),
    path(
        "update_user_row/<int:activity_id>/<int:user_id>",
        views.update_user_row,
        name="update_user_row",
    ),
]



# console.log(`UserId: ${user_dd}, ActivityId: ${ativity_id}, LoanLimit: ${loanLimit}, RestrictLoan: ${restrictLoan}`)
#         fetch(`/manager/update_user_row/${activity_id}/${user_id}`, {
#           method: 'POST',
#           headers: {
#             'Content-Type': 'application/json',
#             'X-CSRFToken': '{{ csrf_token }}'
#           },
#           body: JSON.stringify({
#             loan_limit: loanLimit,
#             restrict_loan: restrictLoan