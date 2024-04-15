from django.shortcuts import render

# Create your views here.
from .managing import (
    dashboard,
    create_chama,
    profile,
    chama,
    chama_join_status,
)

from .chama_investments import invest, withdraw_from_investment
