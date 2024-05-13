from django.shortcuts import render

# Create your views here.
from .membermanagement import dashboard, profile, change_password
from .member_chama import view_chama, join_chama, access_chama, view_chama_members
from .member_transactions import (
    direct_deposit_to_chama,
    from_wallet_to_chama,
    deposit_to_wallet,
    withdraw_from_wallet,
)
from .members_activity import members_tracker
from .profile_update import member_profile_updater, manager_profile_updater
