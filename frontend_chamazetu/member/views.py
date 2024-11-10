from django.shortcuts import render

# Create your views here.
from .membermanagement import dashboard, profile, change_password, process_invite, self_service
from .member_chama import (
    view_chama,
    view_private_chama,
    join_chama,
    access_chama,
    view_chama_members,
    get_about_chama,
    auto_contribute_settings,
    chama_activities,
    get_chama_view,
)
from .activities import (
    join_activity,
    get_activity,
    access_activity,
    view_activity_members,
    get_about_activity,
    activate_auto_contributions,
    deactivate_auto_contributions,
    rotation_contributions,
    get_increase_shares_page,
    increase_shares,
    get_late_joining_activity_page,
    join_activity_late,
    get_disbursement_records,
)
from .member_transactions import (
    from_wallet_to_activity,
    from_wallet_to_select_activity,
    wallet_transactions,
    fix_mpesa_to_wallet_deposit,
)
from .members_activity import members_tracker, fines_tracker
from .profile_update import (
    update_profile_image,
    update_phone_number,
    update_twitter_handle,
    update_linkedin_handle,
    update_facebook_handle,
)

from .table_banking import soft_loans, request_soft_loan, loan_repayment
