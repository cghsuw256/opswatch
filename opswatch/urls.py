from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="staff", permanent=False)),
    path("", include("inventory.urls")),
]
