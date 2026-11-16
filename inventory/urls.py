from django.urls import path

from inventory import views

urlpatterns = [
    path("staff/", views.staff, name="staff"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("support/", views.support, name="support"),
    path("api/internal/token/", views.issue_token, name="issue_token"),
    path("admin/diagnostics/", views.diagnostics_page, name="diagnostics"),
    path("api/internal/diagnose/", views.diagnose_api, name="diagnose_api"),
    path("ops/assistant/", views.assistant_page, name="assistant"),
    path("api/internal/assistant/", views.assistant_api, name="assistant_api"),
    path("health/", views.health, name="health"),
]
