from django.urls import path

from operations import views
from operations.overview import dashboard, service_status

urlpatterns = [
    path("staff/", views.staff, name="staff"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("support/", service_status, name="support"),
    path("admin/setting", views.demo_token_settings, name="demo_token_settings"),
    path("admin/diagnostics/", views.diagnostics_page, name="diagnostics"),
]
