from django.shortcuts import render

# Create your views here.
from .membermanagement import dashboard, profile, change_password
from .member_chama import (
    view_chama,
    join_chama,
    access_chama,
    view_chama_members,
    get_about_chama,
    auto_contribute_settings,
    chama_activities,
)
from .activities import (
    join_activity,
    access_activity,
    view_activity_members,
    get_about_activity,
    activate_auto_contributions,
    deactivate_auto_contributions,
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
