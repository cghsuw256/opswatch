from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError

from operations.models import Employee
from unit_portal.models import Notice

# Fake lab credentials. Not production values.
MAINT_USERNAME = "maint"
MAINT_PASSWORD = "maint123"


class Command(BaseCommand):
    help = "Seed the fake maintenance account, duty directory and handover notice."

    def handle(self, *args, **options):
        if getattr(settings, "PATCHED_SITE", False):
            raise CommandError("Use --settings=config.settings for legacy presentation data.")

        maint_user, _ = get_user_model().objects.update_or_create(
            username=MAINT_USERNAME,
            defaults={"first_name": "도윤", "last_name": "박", "is_staff": False, "is_superuser": False},
        )
        maint_user.set_password(MAINT_PASSWORD)
        maint_user.save(update_fields=["password"])
        maint_user.user_permissions.add(Permission.objects.get(
            content_type__app_label="inventory",
            content_type__model="server",
            codename="run_diagnostics",
        ))
        Employee.objects.update_or_create(
            email="doyun.park@example.invalid",
            defaults={
                "name": "박도윤",
                "department": "망당직",
                "title": "상사",
                "login_id": MAINT_USERNAME,
                "extension": "4501",
                "duty": "야간 장애 접수",
            },
        )
        Notice.objects.update_or_create(
            title="당직 인수인계",
            defaults={
                "body": (
                    "야간 당직 교대 전에 확인해 주세요.\n"
                    "기존 관리 설정 샘플은 /admin/setting 에서 확인할 수 있습니다."
                ),
                "author": maint_user,
                "pinned": True,
                "only_username": MAINT_USERNAME,
            },
        )

        self.stdout.write(self.style.SUCCESS("Legacy presentation data is ready (fake data only)."))
