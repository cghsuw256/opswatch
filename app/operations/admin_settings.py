from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from unit_portal.profiles import get_profile


@never_cache
@login_required
@require_GET
def admin_settings(request):
    if not get_profile(request.user).is_admin:
        raise PermissionDenied
    return JsonResponse({
        "database": {"engine": settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1]},
    })
