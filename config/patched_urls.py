from django.urls import include, path

from patched_portal import views

urlpatterns = [
    path("", include("unit_portal.urls")),
    path("staff/", views.staff, name="staff"),
    path("login/", views.sign_in, name="login"),
    path("logout/", views.sign_out, name="logout"),
    path("admin/diagnostics/", views.diagnostics, name="diagnostics"),
]
