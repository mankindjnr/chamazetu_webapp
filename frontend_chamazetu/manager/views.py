from django.shortcuts import render

# Create your views here.
from .managing import (
    dashboard,
    create_chama,
    profile,
    change_password,
    chama,
    view_chama_members,
    get_about_chama,
)

from .chama_features_edit import (
    new_members,
    activate_chama,
    deactivate_chama,
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
