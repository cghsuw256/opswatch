from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import IntranetPasswordChangeForm
from .models import Notice


def _visible_notices(user):
    notices = Notice.objects.select_related("author__profile")
    if getattr(settings, "PATCHED_SITE", False):
        return notices.filter(only_username="")
    return notices.filter(Q(only_username="") | Q(only_username=user.username))


@login_required
@require_GET
def home(request):
    return render(request, "intranet/home.html", {"notices": _visible_notices(request.user)[:5]})


@login_required
@require_GET
def notices(request):
    return render(request, "intranet/notices.html", {"notices": _visible_notices(request.user)})


@login_required
@require_GET
def notice_detail(request, pk):
    notice = get_object_or_404(_visible_notices(request.user), pk=pk)
    return render(request, "intranet/notice_detail.html", {"notice": notice})


@login_required
@require_GET
def profile(request):
    return render(request, "intranet/profile.html", {"password_form": IntranetPasswordChangeForm(request.user)})


@login_required
@require_POST
def password(request):
    form = IntranetPasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "비밀번호가 변경되었습니다. 다른 기기의 로그인은 모두 해제되었습니다.")
        return redirect("intranet:profile")
    return render(request, "intranet/profile.html", {"password_form": form}, status=400)
