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
)


