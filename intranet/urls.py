from django.urls import path

from . import views

app_name = "intranet"

urlpatterns = [
    path("", views.home, name="home"),
    path("notices/", views.notices, name="notices"),
    path("notices/new/", views.notice_new, name="notice_new"),
    path("notices/<int:pk>/", views.notice_detail, name="notice_detail"),
    path("notices/<int:pk>/delete/", views.notice_delete, name="notice_delete"),
    path("board/", views.board, name="board"),
    path("board/new/", views.post_new, name="post_new"),
    path("board/<int:pk>/", views.post_detail, name="post_detail"),
    path("board/<int:pk>/delete/", views.post_delete, name="post_delete"),
    path("board/<int:pk>/comment/", views.comment_create, name="comment_create"),
    path("approvals/", views.approvals, name="approvals"),
    path("approvals/new/", views.approval_new, name="approval_new"),
    path("approvals/<int:pk>/", views.approval_detail, name="approval_detail"),
    path("approvals/<int:pk>/decide/", views.approval_decide, name="approval_decide"),
    path("calendar/", views.calendar, name="calendar"),
    path("calendar/new/", views.event_create, name="event_create"),
    path("calendar/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("people/", views.people, name="people"),
    path("me/", views.profile, name="profile"),
    path("me/password/", views.password, name="password"),
]
