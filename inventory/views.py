import json

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from inventory.charts import alert_evolution, decorate_servers
from inventory.models import Employee, Inspection, Server
from inventory.services.diagnostics import (
    DiagnosticsBusy,
    DiagnosticsDisabled,
    DiagnosticsInvalid,
    run_ping_diagnosis,
)


def _json_error(message, status):
    return JsonResponse({"ok": False, "error": message}, status=status)


@require_GET
def health(request):
    return JsonResponse({"status": "ok", "service": "opswatch"})


@require_GET
def staff(request):
    employees = Employee.objects.all()
    return render(request, "inventory/staff.html", {"employees": employees})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        # INTENTIONAL EDUCATIONAL WEAKNESS: no attempt counter / account lockout.
        if form.is_valid():
            login(request, form.get_user())
            return redirect("dashboard")
    return render(request, "inventory/login.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("login")


@require_GET
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    servers = decorate_servers(list(Server.objects.all()))
    inspections = Inspection.objects.select_related("server")[:12]
    return render(
        request,
        "inventory/dashboard.html",
        {
            "servers": servers,
            "inspections": inspections,
            "seed_metrics": any(server.seed_metrics for server in servers),
            "alert_points": alert_evolution(servers),
            "agent_total": len(servers),
            "agent_warn": sum(1 for server in servers if server.status != "ok"),
        },
    )


@require_GET
def support(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "inventory/support.html")


@require_GET
def support_script(request):
    if not request.user.is_authenticated:
        return redirect("login")
    path = settings.SUPPORT_SCRIPT_PATH
    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename="opswatch-healthcheck.sh",
        content_type="text/x-shellscript",
    )


@require_GET
def diagnostics_page(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(
        request,
        "inventory/diagnostics.html",
        {
            "diagnostics_enabled": settings.OPSWATCH_RUNTIME == "container"
            and settings.OPSWATCH_ENABLE_DIAGNOSTICS,
        },
    )


@require_POST
def diagnose_api(request):
    if not request.user.is_authenticated:
        return _json_error("인증이 필요합니다.", 401)

    token = request.headers.get("X-OpsWatch-Token", "")
    target = ""
    content_type = request.content_type or ""
    if content_type.startswith("application/json"):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return _json_error("JSON 형식이 올바르지 않습니다.", 400)
        token = token or str(payload.get("token") or "")
        target = str(payload.get("target") or "")
    else:
        token = token or request.POST.get("token", "")
        target = request.POST.get("target", "")

    if token != settings.OPSWATCH_INTERNAL_TOKEN:
        return _json_error("내부 API 토큰이 올바르지 않습니다.", 403)

    try:
        result = run_ping_diagnosis(target)
    except DiagnosticsDisabled as exc:
        return _json_error(str(exc), 403)
    except DiagnosticsInvalid as exc:
        return _json_error(str(exc), 400)
    except DiagnosticsBusy as exc:
        return _json_error(str(exc), 429)

    return JsonResponse(
        {
            "ok": result.status == "ok",
            "status": result.status,
            "output": result.output,
            "timed_out": result.timed_out,
        }
    )
