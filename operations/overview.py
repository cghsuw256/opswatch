from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .charts import alert_evolution
from .models import Inspection, Server


@login_required
@require_GET
def dashboard(request):
    servers = list(Server.objects.all())
    return render(request, "inventory/dashboard.html", {
        "servers": servers,
        "alert_chart": alert_evolution(servers),
        "inspections": Inspection.objects.select_related("server")[:12],
    })


@login_required
@require_GET
def service_status(request):
    return render(request, "inventory/service_status.html", {"servers": Server.objects.only("hostname", "status")})
