from django.apps import AppConfig


class IntranetConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "intranet"
    verbose_name = "부대 인트라넷"

    def ready(self):
        from . import signals  # noqa: F401
