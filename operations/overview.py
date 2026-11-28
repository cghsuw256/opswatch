from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import Inspection, Server


@login_required
@require_GET
def dashboard(request):
    return render(request, "inventory/dashboard.html", {
        "servers": Server.objects.all(),
        "inspections": Inspection.objects.select_related("server")[:12],
    })


@login_required
@require_GET
def service_status(request):
    return render(request, "inventory/service_status.html", {"servers": Server.objects.only("hostname", "status")})
