from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .profiles import get_profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="intranet.ensure_user_profile")
def ensure_user_profile(sender, instance, raw=False, **kwargs):
    if not raw:
        get_profile(instance)
