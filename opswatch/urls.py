from django.urls import include, path

urlpatterns = [
    path("", include("intranet.urls")),
    path("", include("inventory.urls")),
]
