import json

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from inventory.charts import alert_evolution
from inventory.models import Employee, Inspection, Server
from inventory.services.diagnostics import (
    DiagnosticsBusy,
    DiagnosticsDisabled,
    DiagnosticsInvalid,
    run_ping_diagnosis,
)
from inventory.services.assistant import answer_ops_request


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
    servers = list(Server.objects.all())
    inspections = list(Inspection.objects.select_related("server")[:12])
    return render(
        request,
        "inventory/dashboard.html",
        {
            "servers": servers,
            "inspections": inspections,
            "seed_metrics": any(server.seed_metrics for server in servers),
            "alert_chart": alert_evolution(servers),
            "agent_total": len(servers),
            "agent_warn": sum(server.status == Server.STATUS_WARN for server in servers),
            "agent_ok": sum(server.status == Server.STATUS_OK for server in servers),
            "agent_down": sum(server.status == Server.STATUS_DOWN for server in servers),
            "inspection_passed": sum(row.passed for row in inspections),
            "inspection_failed": sum(not row.passed for row in inspections),
        },
    )


@require_GET
def support(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "inventory/support.html")


@require_GET
def issue_token(request):
    if not request.user.is_authenticated:
        return _json_error("인증이 필요합니다.", 401)
    # INTENTIONAL EDUCATIONAL WEAKNESS: not real issuance.
    # Every authenticated user receives the same static lab token.
    # No expiry, rotation, or per-user binding.
    request.session["opswatch_internal_token"] = settings.OPSWATCH_INTERNAL_TOKEN
    return JsonResponse(
        {
            "token": settings.OPSWATCH_INTERNAL_TOKEN,
            "token_type": "internal",
            "expires_in": None,
        }
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
            "diagnostics_token": request.session.get("opswatch_internal_token", ""),
        },
    )


@require_GET
def assistant_page(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(
        request,
        "inventory/assistant.html",
        {
            "diagnostics_enabled": settings.OPSWATCH_RUNTIME == "container"
            and settings.OPSWATCH_ENABLE_DIAGNOSTICS,
            "diagnostics_token": request.session.get("opswatch_internal_token", ""),
        },
    )


def _read_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


@csrf_exempt  # INTENTIONAL EDUCATIONAL WEAKNESS: same static token as diagnose_api.
@require_POST
def assistant_api(request):
    payload = _read_json(request)
    if payload is None:
        return _json_error("JSON 형식이 올바르지 않습니다.", 400)
    token = request.headers.get("X-OpsWatch-Token", "") or str(payload.get("token") or "")
    if token != settings.OPSWATCH_INTERNAL_TOKEN:
        return _json_error("내부 API 토큰이 올바르지 않습니다.", 403)
    message = str(payload.get("message") or "").strip()
    target = str(payload.get("target") or "")
    if not message:
        return _json_error("요청 내용을 입력하세요.", 400)
    try:
        reply, result = answer_ops_request(message, target)
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
            "reply": reply,
            "timed_out": result.timed_out,
        }
    )


@csrf_exempt  # INTENTIONAL EDUCATIONAL WEAKNESS: no session/CSRF. Static token is enough.
@require_POST
def diagnose_api(request):
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
