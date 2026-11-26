from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from operations.charts import alert_evolution
from operations.models import Inspection, Server


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
