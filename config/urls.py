from django.urls import include, path

urlpatterns = [
    path("", include("unit_portal.urls")),
    path("", include("operations.urls")),
]
