from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from operations.models import Employee, Inspection, Server
from unit_portal.demo import seed_demo_inbox
from unit_portal.models import Notice

# Fictional credentials for the local legacy demonstration.
MAINT_USERNAME = "maint"
MAINT_PASSWORD = "maint123"


class Command(BaseCommand):
    help = "Seed local legacy accounts, contacts, and operations examples."

    def add_arguments(self, parser):
        parser.add_argument("--keep-password", action="store_true")

    @transaction.atomic
    def handle(self, *args, keep_password, **options):
        if getattr(settings, "PATCHED_SITE", False):
            raise CommandError("Use --settings=config.settings for legacy presentation data.")

        maint_user, created = get_user_model().objects.update_or_create(
            username=MAINT_USERNAME,
            defaults={"first_name": "도윤", "last_name": "박", "is_staff": False, "is_superuser": False},
        )
        if created or not keep_password:
            maint_user.set_password(MAINT_PASSWORD)
            maint_user.save(update_fields=["password"])
        maint_user.user_permissions.add(Permission.objects.get(
            content_type__app_label="inventory",
            content_type__model="server",
            codename="run_diagnostics",
        ))
        seed_demo_inbox(maint_user)
        for name, department, title, email, extension in (
            ("김서연", "인력관리", "8급 군무원", "seoyeon.kim", "4102"),
            ("이민준", "체계운영", "선임", "minjun.lee", "4307"),
            ("최하린", "상황실", "하사", "harin.choi", "4408"),
        ):
            Employee.objects.get_or_create(email=f"{email}@example.invalid", defaults={
                "name": name, "department": department, "title": title, "extension": extension,
            })

        for hostname, address, role, status, cpu, memory, rack, inspector, summary, detail, passed in (
            ("web-01.lab.local", "192.0.2.11", "웹 프론트", Server.STATUS_OK, 23, 41, "LAB-RACK-A",
             "이민준", "TLS 인증서 만료일 확인", "실습용 인증서 점검 기록입니다.", True),
            ("db-01.lab.local", "192.0.2.12", "데이터베이스", Server.STATUS_WARN, 61, 74, "LAB-RACK-A",
             "박도윤", "디스크 사용률 주의", "실습용 저장 기록입니다.", False),
            ("mon-01.lab.local", "192.0.2.13", "모니터링", Server.STATUS_OK, 12, 28, "LAB-RACK-B",
             "최하린", "헬스체크 정상", "실습용 상태 기록입니다.", True),
        ):
            server, _ = Server.objects.get_or_create(hostname=hostname, defaults={
                "address": address, "role": role, "status": status, "cpu_percent": cpu,
                "memory_percent": memory, "location": rack, "seed_metrics": False,
            })
            Inspection.objects.get_or_create(server=server, summary=summary, defaults={
                "inspected_at": timezone.now(), "inspector_name": inspector,
                "detail": detail, "passed": passed,
            })

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

        if options["verbosity"]:
            self.stdout.write(self.style.SUCCESS("Legacy presentation data is ready (fake data only)."))
