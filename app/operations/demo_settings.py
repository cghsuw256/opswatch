from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def demo_token_settings(request):
    return JsonResponse({
        "database": {
            "engine": "postgresql",
            "host": "db.example.invalid",
            "port": 5432,
            "name": "opswatch_demo",
            "username": "opswatch_demo",
            "password": "demo-db-password-not-valid",
        },
        "maintenance_account": {
            "username": "maint",
            "password": "demo-maint-password-not-valid",
        },
        "demo_only": True,
    })
