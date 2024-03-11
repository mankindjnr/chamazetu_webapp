from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("signin/<str:role>", views.signin, name="signin"),
    path("signup/<str:role>", views.signup, name="signup"),
    path("signout", views.signout, name="signout"),
    path("activate/<role>/<uidb64>/<token>", views.activate, name="activate"),
]
