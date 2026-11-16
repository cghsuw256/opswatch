from .models import Approval
from .profiles import get_profile


def intranet_shell(request):
    if not request.user.is_authenticated:
        return {"is_intranet_admin": False, "pending_approval_count": 0}
    profile = get_profile(request.user)
    return {
        "profile": profile,
        "is_intranet_admin": profile.is_admin,
        "pending_approval_count": Approval.objects.filter(approver=request.user, status="pending").count(),
    }
