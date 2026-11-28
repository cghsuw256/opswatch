from django.conf import settings

from .profiles import get_profile


def intranet_shell(request):
    site = {"patched_site": getattr(settings, "PATCHED_SITE", False)}
    if not request.user.is_authenticated:
        return site
    profile = get_profile(request.user)
    return {
        **site,
        "profile": profile,
    }
