from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("chama.urls")),
    path("member/", include("member.urls")),
    path("manager/", include("manager.urls")),
]
