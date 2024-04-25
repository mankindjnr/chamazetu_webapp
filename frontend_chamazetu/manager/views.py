from django.shortcuts import render

# Create your views here.
from .managing import (
    dashboard,
    create_chama,
    profile,
    change_password,
    chama,
    chama_join_status,
    activate_deactivate_chama,
)

from .chama_investments import invest, withdraw_from_investment
