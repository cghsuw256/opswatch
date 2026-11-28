from django.urls import path

from . import views

app_name = "intranet"

urlpatterns = [
    path("", views.home, name="home"),
    path("notices/", views.notices, name="notices"),
    path("notices/<int:pk>/", views.notice_detail, name="notice_detail"),
    path("me/", views.profile, name="profile"),
    path("me/password/", views.password, name="password"),
]
