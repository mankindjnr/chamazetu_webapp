from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signin/<str:role>', views.signin, name='signin'),
    path('signup/<str:role>', views.signup, name='signup'),
    path('activate/<uidb64>/<token>', views.activate, name='activate'),
    path('memberdashboard', views.memberdashboard, name='memberdashboard'),
    path('managerdashboard', views.managerdashboard, name='managerdashboard'),
    path('profile', views.profile, name='profile'),
]