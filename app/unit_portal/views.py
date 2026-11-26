import calendar as month_calendar
import datetime as dt
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import ApprovalForm, CommentForm, DecisionForm, EventForm, IntranetPasswordChangeForm, NoticeForm, PostForm, ProfileForm
from .models import Approval, CATEGORIES, Event, Notice, Post, Profile
from .profiles import get_profile


SAVED = "저장되었습니다."
POSTED = "등록되었습니다."
DELETED = "삭제되었습니다."


def _admin(user):
    return get_profile(user).is_admin


def _require_admin(user):
    if not _admin(user):
        raise PermissionDenied("권한이 없습니다.")


def _render(request, template, context=None, status=200):
    return render(request, f"intranet/{template}.html", context or {}, status=status)


def _visible_events(user):
    return Event.objects.filter(Q(scope="company") | Q(owner=user)).select_related("owner__profile")


def _ensure_profiles():
    for user in get_user_model().objects.filter(profile__isnull=True).iterator():
        get_profile(user)


@login_required
@require_GET
def home(request):
    today = timezone.localdate()
    incoming = Approval.objects.filter(approver=request.user, status="pending")
    events = _visible_events(request.user)
    return _render(request, "home", {
        "today": today,
        "inbox_count": incoming.count(),
        "mine_count": Approval.objects.filter(drafter=request.user, status="pending").count(),
        "today_event_count": events.filter(date=today).count(),
        "new_notice_count": Notice.objects.filter(created__date__gte=today - dt.timedelta(days=7)).count(),
        "notices": Notice.objects.select_related("author__profile")[:5],
        "pending_approvals": incoming.select_related("drafter__profile")[:5],
        "events": events.filter(date__gte=today)[:5],
        "posts": Post.objects.select_related("author__profile").annotate(comment_count=Count("comments"))[:5],
    })


@login_required
@require_GET
def notices(request):
    return _render(request, "notices", {"notices": Notice.objects.select_related("author__profile")})


@login_required
@require_http_methods(["GET", "POST"])
def notice_new(request):
    _require_admin(request.user)
    form = NoticeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        notice = form.save(commit=False)
        notice.author = request.user
        notice.save()
        messages.success(request, POSTED)
        return redirect("intranet:notice_detail", pk=notice.pk)
    return _render(request, "notice_form", {"form": form}, status=400 if request.method == "POST" else 200)


@login_required
@require_GET
def notice_detail(request, pk):
    notice = get_object_or_404(Notice.objects.select_related("author__profile"), pk=pk)
    return _render(request, "notice_detail", {"notice": notice, "can_delete": _admin(request.user)})


@login_required
@require_POST
def notice_delete(request, pk):
    _require_admin(request.user)
    get_object_or_404(Notice, pk=pk).delete()
    messages.success(request, DELETED)
    return redirect("intranet:notices")


@login_required
@require_GET
def board(request):
    category = request.GET.get("cat", "")
    category = category if category in CATEGORIES else ""
    term = request.GET.get("q", "").strip()[:50]
    posts = Post.objects.select_related("author__profile").annotate(comment_count=Count("comments"))
    if category:
        posts = posts.filter(category=category)
    if term:
        posts = posts.filter(Q(title__icontains=term) | Q(body__icontains=term))
    page = Paginator(posts, 10).get_page(request.GET.get("page"))
    return _render(request, "board", {"posts": page.object_list, "page_obj": page, "q": term, "category": category, "categories": CATEGORIES, "query_string": urlencode({"cat": category, "q": term})})


@login_required
@require_http_methods(["GET", "POST"])
def post_new(request):
    form = PostForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        messages.success(request, POSTED)
        return redirect("intranet:post_detail", pk=post.pk)
    return _render(request, "post_form", {"form": form}, status=400 if request.method == "POST" else 200)


def _post_context(request, post, form=None):
    return {"post": post, "comments": post.comments.select_related("author__profile"), "comment_form": form if form is not None else CommentForm(), "can_delete": post.author_id == request.user.pk or _admin(request.user)}


@login_required
@require_GET
def post_detail(request, pk):
    post = get_object_or_404(Post.objects.select_related("author__profile"), pk=pk)
    Post.objects.filter(pk=pk).update(views=F("views") + 1)
    post.views += 1
    return _render(request, "post_detail", _post_context(request, post))


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author_id != request.user.pk and not _admin(request.user):
        raise PermissionDenied("권한이 없습니다.")
    post.delete()
    messages.success(request, DELETED)
    return redirect("intranet:board")


@login_required
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(Post.objects.select_related("author__profile"), pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        messages.success(request, POSTED)
        return redirect("intranet:post_detail", pk=pk)
    return _render(request, "post_detail", _post_context(request, post, form), status=400)


@login_required
@require_GET
def approvals(request):
    tab = "sent" if request.GET.get("tab") == "sent" else "inbox"
    rows = Approval.objects.select_related("drafter__profile", "approver__profile")
    if tab == "sent":
        rows = rows.filter(drafter=request.user)
    else:
        rows = rows.filter(approver=request.user).annotate(pending_first=Case(When(status="pending", then=Value(0)), default=Value(1), output_field=IntegerField())).order_by("pending_first", "-created", "-pk")
    return _render(request, "approvals", {"approvals": rows, "tab": tab})


@login_required
@require_http_methods(["GET", "POST"])
def approval_new(request):
    _ensure_profiles()
    form = ApprovalForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        approval = form.save(commit=False)
        approval.drafter = request.user
        approval.save()
        messages.success(request, POSTED)
        return redirect("intranet:approval_detail", pk=approval.pk)
    return _render(request, "approval_form", {"form": form}, status=400 if request.method == "POST" else 200)


def _load_approval(request, pk):
    rows = Approval.objects.select_related("drafter__profile", "approver__profile")
    if not _admin(request.user):
        rows = rows.filter(Q(drafter=request.user) | Q(approver=request.user))
    return get_object_or_404(rows, pk=pk)


def _approval_context(request, approval, form=None):
    return {"approval": approval, "can_decide": approval.approver_id == request.user.pk and approval.status == "pending", "decision_form": form if form is not None else DecisionForm()}


@login_required
@require_GET
def approval_detail(request, pk):
    approval = _load_approval(request, pk)
    return _render(request, "approval_detail", _approval_context(request, approval))


@login_required
@require_POST
def approval_decide(request, pk):
    approval = _load_approval(request, pk)
    if approval.approver_id != request.user.pk or approval.status != "pending" or request.POST.get("action") not in ("approve", "reject"):
        raise PermissionDenied("처리할 수 없는 문서입니다.")
    form = DecisionForm(request.POST)
    if not form.is_valid():
        return _render(request, "approval_detail", _approval_context(request, approval, form), status=400)
    changed = Approval.objects.filter(pk=pk, approver=request.user, status="pending").update(status="approved" if form.cleaned_data["action"] == "approve" else "rejected", comment=form.cleaned_data["comment"], decided=timezone.now())
    if not changed:
        raise PermissionDenied("처리할 수 없는 문서입니다.")
    messages.success(request, "결재가 처리되었습니다.")
    return redirect("intranet:approval_detail", pk=pk)


def _calendar_context(request, form=None):
    today = timezone.localdate()
    match = re.fullmatch(r"(\d{4})-(\d{2})", request.GET.get("ym", ""))
    year, month = (int(match[1]), int(match[2])) if match else (today.year, today.month)
    if not 2000 <= year <= 2100 or not 1 <= month <= 12:
        year, month = today.year, today.month
    dates = month_calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    events = list(_visible_events(request.user).filter(date__range=(dates[0][0], dates[-1][-1])))
    by_day = {}
    admin = _admin(request.user)
    for event in events:
        by_day.setdefault(event.date, []).append(event)
    weeks = [[{"date": day, "day": day.day, "in_month": day.month == month, "is_today": day == today, "events": by_day.get(day, [])} for day in week] for week in dates]
    first = dt.date(year, month, 1)
    return {"month": first.strftime("%Y-%m"), "previous_month": (first - dt.timedelta(days=1)).strftime("%Y-%m"), "next_month": (dt.date(year, month, 28) + dt.timedelta(days=7)).strftime("%Y-%m"), "weeks": weeks, "events": [event for event in events if event.date.month == month], "form": form if form is not None else EventForm(is_admin=admin, initial={"date": today, "scope": "personal"})}


@login_required
@require_GET
def calendar(request):
    return _render(request, "calendar", _calendar_context(request))


@login_required
@require_POST
def event_create(request):
    is_admin = _admin(request.user)
    data = request.POST.copy()
    if not is_admin:
        data["scope"] = "personal"
    form = EventForm(data, is_admin=is_admin)
    if form.is_valid():
        event = form.save(commit=False)
        event.owner = request.user
        event.save()
        messages.success(request, SAVED)
        return redirect(f"{reverse('intranet:calendar')}?{urlencode({'ym': event.date.strftime('%Y-%m')})}")
    return _render(request, "calendar", _calendar_context(request, form), status=400)


@login_required
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.owner_id != request.user.pk and not _admin(request.user):
        raise PermissionDenied("권한이 없습니다.")
    event.delete()
    messages.success(request, DELETED)
    month = request.POST.get("ym", "")
    return redirect(f"{reverse('intranet:calendar')}?{urlencode({'ym': month})}" if re.fullmatch(r"\d{4}-\d{2}", month) else "intranet:calendar")


@login_required
@require_GET
def people(request):
    _ensure_profiles()
    term = request.GET.get("q", "").strip()[:30]
    departments = list(Profile.objects.order_by("dept").values_list("dept", flat=True).distinct())
    dept = request.GET.get("dept", "")
    dept = dept if dept in departments else ""
    rows = Profile.objects.select_related("user")
    if dept:
        rows = rows.filter(dept=dept)
    if term:
        rows = rows.filter(Q(name__icontains=term) | Q(title__icontains=term) | Q(email__icontains=term))
    return _render(request, "people", {"people": rows, "departments": departments, "dept": dept, "q": term})


def _profile_context(request, form=None, password_form=None):
    return {"form": form if form is not None else ProfileForm(instance=get_profile(request.user)), "password_form": password_form if password_form is not None else IntranetPasswordChangeForm(request.user)}


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    form = ProfileForm(request.POST if request.method == "POST" else None, instance=get_profile(request.user))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, SAVED)
        return redirect("intranet:profile")
    return _render(request, "profile", _profile_context(request, form=form), status=400 if request.method == "POST" else 200)


@login_required
@require_POST
def password(request):
    form = IntranetPasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "비밀번호가 변경되었습니다. 다른 기기의 로그인은 모두 해제되었습니다.")
        return redirect("intranet:profile")
    return _render(request, "profile", _profile_context(request, password_form=form), status=400)
