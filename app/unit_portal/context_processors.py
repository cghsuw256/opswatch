from django.conf import settings

from .models import Approval
from .profiles import get_profile


def intranet_shell(request):
    site = {"patched_site": getattr(settings, "PATCHED_SITE", False)}
    if not request.user.is_authenticated:
        return {**site, "is_intranet_admin": False, "pending_approval_count": 0}
    profile = get_profile(request.user)
    return {
        **site,
        "profile": profile,
        "is_intranet_admin": profile.is_admin,
        "pending_approval_count": Approval.objects.filter(approver=request.user, status="pending").count(),
    }
