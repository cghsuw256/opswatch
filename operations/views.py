from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from operations.models import Employee


@require_GET
def staff(request):
    employees = Employee.objects.all()
    return render(request, "inventory/staff.html", {"employees": employees})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("intranet:home")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            login(request, form.get_user())
            return redirect("intranet:home")
    return render(request, "inventory/login.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("login")


@never_cache
@require_GET
def legacy_settings(request):
    payload = (Path(__file__).parent / "admin_setting.json").read_bytes()
    return HttpResponse(payload, content_type="application/json")


@login_required
@permission_required("inventory.run_diagnostics", raise_exception=True)
@require_http_methods(["GET", "POST"])
def diagnostics_page(request):
    roster = None
    if request.method == "POST" and request.POST.get("target", "").strip() == "127.0.0.1; cat /opt/challenge/unit_members.csv":
        ping = subprocess.run(["ping", "-n", "2", "127.0.0.1"], capture_output=True, timeout=5)
        roster = ping.stdout.decode("cp949", errors="replace") + "\n" + (settings.BASE_DIR / "presentation" / "부대원_정보_예시.csv").read_text(encoding="utf-8-sig")
    return render(request, "inventory/diagnostics.html", {"roster": roster})
