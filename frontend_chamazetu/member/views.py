from django.shortcuts import render

# Create your views here.
from .membermanagement import dashboard, profile
from .member_chama import view_chama, join_chama, access_chama
from .member_transactions import deposit_to_chama
