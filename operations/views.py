import subprocess

from pathlib import Path

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from operations.models import Employee
from operations.posix_shell import run as run_posix


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
@require_GET
def diagnostics_page(request):
    param = request.GET.get("target", "").strip()
    context = {
        "target": param,
        "diagnostic_requested": "target" in request.GET,
    }
    if not context["diagnostic_requested"]:
        return render(request, "inventory/diagnostics.html", context)
    if not param:
        context["diagnostic_error"] = "진단 대상을 입력하세요."
        return render(request, "inventory/diagnostics.html", context, status=400)

    command = f"ping -c 3 {param}"
    context["command"] = command

    try:
        # Intentionally vulnerable legacy behavior for this local command-injection lab.
        result = run_posix(command, cwd=settings.BASE_DIR, timeout=12)
    except subprocess.TimeoutExpired as error:
        partial_output = (error.stdout or b"") + (error.stderr or b"")
        context.update(
            diagnostic_error="진단 명령 실행 시간이 초과되었습니다.",
            output=partial_output.decode("utf-8", errors="replace").strip(),
            result_label="시간 초과",
            result_status="down",
        )
        return render(request, "inventory/diagnostics.html", context, status=504)
    except OSError:
        context.update(
            diagnostic_error="진단 명령을 시작하지 못했습니다.",
            result_label="실행 실패",
            result_status="down",
        )
        return render(request, "inventory/diagnostics.html", context, status=500)

    output = f"{result.stdout}{result.stderr}".strip() or "(출력 없음)"
    context.update(
        output=output,
        result_label=f"종료 코드 {result.returncode}",
        result_status="ok" if result.returncode == 0 else "down",
    )
    return render(request, "inventory/diagnostics.html", context)
