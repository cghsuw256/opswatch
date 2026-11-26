from django.urls import include, path

from operations.admin_settings import admin_settings
from operations.overview import dashboard
from patched_portal import views

urlpatterns = [
    path("", include("unit_portal.urls")),
    path("staff/", views.staff, name="staff"),
    path("login/", views.sign_in, name="login"),
    path("logout/", views.sign_out, name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("support/", views.status, name="support"),
    path("admin/setting", admin_settings, name="admin_settings"),
    path("admin/diagnostics/", views.diagnostics, name="diagnostics"),
    path("health/", views.health, name="health"),
]
