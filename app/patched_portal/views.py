from time import time

from django import forms
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from operations.models import Employee, Inspection, Server

from .models import LoginAttempt

LOGIN_WINDOW_SECONDS = 60
LOGIN_ATTEMPTS_PER_WINDOW = 10


def _login_retry_after(source):
    with transaction.atomic():
        now = int(time())
        window = now // LOGIN_WINDOW_SECONDS
        LoginAttempt.objects.filter(window__lt=window).delete()
        attempt, _ = LoginAttempt.objects.get_or_create(source=source, defaults={"window": window})
        if attempt.count >= LOGIN_ATTEMPTS_PER_WINDOW:
            return LOGIN_WINDOW_SECONDS - now % LOGIN_WINDOW_SECONDS
        attempt.count += 1
        attempt.save(update_fields=["count"])
    return 0


@never_cache
@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("intranet:home")
    if request.method == "POST":
        retry_after = _login_retry_after(request.META.get("REMOTE_ADDR") or "unknown")
        if retry_after:
            response = render(request, "inventory/login.html", {"login_throttled": True}, status=429)
            response["Retry-After"] = str(retry_after)
            return response
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("intranet:home")
    else:
        form = AuthenticationForm(request)
    return render(request, "inventory/login.html", {"form": form})


@require_POST
def sign_out(request):
    logout(request)
    return redirect("login")


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def staff(request):
    employees = Employee.objects.values("name", "department", "title", "extension")
    return render(request, "inventory/staff.html", {"employees": employees})


@login_required
@require_GET
def status(request):
    servers = Server.objects.only("hostname", "status")
    return render(request, "patched_portal/status.html", {"servers": servers})


class HostForm(forms.Form):
    server = forms.ModelChoiceField(label="등록 호스트", queryset=Server.objects.all())


@never_cache
@login_required
@permission_required("inventory.run_diagnostics", raise_exception=True)
@require_http_methods(["GET", "POST"])
def diagnostics(request):
    form = HostForm(request.POST if request.method == "POST" else None)
    if request.method == "GET":
        return render(request, "patched_portal/diagnostics.html", {"form": form})
    if not form.is_valid():
        return render(request, "patched_portal/diagnostics.html", {"form": form}, status=400)
    server = form.cleaned_data["server"]
    inspection = Inspection.objects.filter(server=server).order_by("-inspected_at", "-pk").first()
    return render(request, "patched_portal/diagnostics.html", {
        "form": form,
        "server": server,
        "inspection": inspection,
    })
