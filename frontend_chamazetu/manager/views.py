from django.shortcuts import render

# Create your views here.
from .managing import (
    dashboard,
    create_chama,
    create_activity,
    profile,
    change_password,
    chama,
    view_chama_members,
    get_about_chama,
    chama_activity,
    new_activity_members,
    deactivate_activate_activity,
    restart_activity,
    delete_activity,
    send_invite_to_members,
    send_activity_invite_to_all,
)

from .chama_features_edit import (
    accept_new_chama_members,
    activate_deactivate_chama,
    delete_chama_by_id,
    update_chama_description,
    update_chama_mission,
    update_chama_vision,
    add_chama_faqs,
    add_chama_rules,
    delete_chama_rule,
    delete_chama_faq,
)

from .track_members import members_tracker

from .chama_investments import invest, withdraw_from_investment

from .manage_activities import (
    rotating_order,
    create_random_rotation_order,
    disburse_funds,
    fines_tracker,
    order_management,
    merry_go_round_share_increase,
    allow_new_activity_members,
    investment_marketplace,
    set_last_contribution_date,
    transfer_fines,
    admin_fees,
    remove_member_from_activity,
    search_for_members_by_names,
)

from .manage_members import membership_management, allow_new_members

from .table_banking import (
    get_soft_loans,
    set_update_table_banking_interest_rate,
    activity_settings,
    update_loan_approval_settings,
    loan_eligibility,
    restrict_user,
    allow_user,
    approve_loan,
    decline_loan,
    disburse_dividends,
    dividend_disbursement,
    update_user_row,
)


from .merry_go_round import merry_go_round_settings, search_for_members_by_order_number, swap_members_order_in_rotation

