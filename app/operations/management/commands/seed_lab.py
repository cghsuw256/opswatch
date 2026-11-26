from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.utils import timezone

from operations.models import Employee, Inspection, Server
from unit_portal.models import Notice

# Fake lab credentials. Not production values.
MAINT_USERNAME = "maint"
MAINT_PASSWORD = "maint123"


class Command(BaseCommand):
    help = "Idempotently seed fake employees, lab login accounts, servers, and inspections."

    def handle(self, *args, **options):
        user_model = get_user_model()
        diagnostic_permission = Permission.objects.get(
            content_type__app_label="inventory",
            content_type__model="server",
            codename="run_diagnostics",
        )
        # Fake lab credentials, intentionally weak for the local exercise.
        accounts = [
            (MAINT_USERNAME, MAINT_PASSWORD, "maint@opswatch.lab", "도윤", "박"),
            ("seoyeon", "seoyeon123", "seoyeon.kim@opswatch.lab", "서연", "김"),
            ("minjun", "minjun123", "minjun.lee@opswatch.lab", "민준", "이"),
            ("harin", "harin123", "harin.choi@opswatch.lab", "하린", "최"),
        ]
        for username, password, email, first_name, last_name in accounts:
            user, _created = user_model.objects.update_or_create(
                username=username,
                defaults={
                    "is_staff": False,
                    "is_superuser": False,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )
            user.set_password(password)
            user.save()
            if username == MAINT_USERNAME:
                user.user_permissions.add(diagnostic_permission)
            else:
                user.user_permissions.remove(diagnostic_permission)

        employees = [
            {
                "email": "seoyeon.kim@opswatch.lab",
                "name": "김서연",
                "department": "인력관리",
                "title": "8급 군무원",
                "login_id": "seoyeon",
                "extension": "4102",
                "duty": "교육망 공지 및 계정 신청 안내",
            },
            {
                "email": "minjun.lee@opswatch.lab",
                "name": "이민준",
                "department": "체계운영",
                "title": "선임",
                "login_id": "minjun",
                "extension": "4307",
                "duty": "호스트 점검 일정 조율",
            },
            {
                "email": "doyun.park@opswatch.lab",
                "name": "박도윤",
                "department": "망당직",
                "title": "상사",
                "login_id": MAINT_USERNAME,
                "extension": "4501",
                "duty": "야간 장애 접수. 콘솔 로그인 ID는 내선 안내와 동일합니다.",
            },
            {
                "email": "harin.choi@opswatch.lab",
                "name": "최하린",
                "department": "상황실",
                "title": "하사",
                "login_id": "harin",
                "extension": "4408",
                "duty": "시드 지표 대시보드 확인",
            },
        ]
        for item in employees:
            Employee.objects.update_or_create(email=item["email"], defaults=item)

        servers = [
            {
                "hostname": "web-01.lab.local",
                "address": "10.32.0.11",
                "role": "웹 프론트",
                "status": Server.STATUS_OK,
                "cpu_percent": 23,
                "memory_percent": 41,
                "location": "LAB-RACK-A",
                "seed_metrics": True,
            },
            {
                "hostname": "db-01.lab.local",
                "address": "10.32.0.12",
                "role": "MySQL 실습",
                "status": Server.STATUS_WARN,
                "cpu_percent": 61,
                "memory_percent": 74,
                "location": "LAB-RACK-A",
                "seed_metrics": True,
            },
            {
                "hostname": "mon-01.lab.local",
                "address": "10.32.0.13",
                "role": "모니터링",
                "status": Server.STATUS_OK,
                "cpu_percent": 12,
                "memory_percent": 28,
                "location": "LAB-RACK-B",
                "seed_metrics": True,
            },
        ]
        host_map = {}
        for item in servers:
            obj, _ = Server.objects.update_or_create(hostname=item["hostname"], defaults=item)
            host_map[obj.hostname] = obj

        now = timezone.now()
        inspection_rows = [
            (
                "web-01.lab.local",
                now - timedelta(hours=6),
                "이민준",
                "TLS 인증서 만료일 확인",
                "실습용 자체 서명 인증서. 운영 인증서 아님.",
                True,
            ),
            (
                "db-01.lab.local",
                now - timedelta(hours=4),
                "박도윤",
                "디스크 사용률 주의",
                "시드 데이터 기준 74%. 실제 호스트 디스크와 무관.",
                False,
            ),
            (
                "mon-01.lab.local",
                now - timedelta(hours=2),
                "최하린",
                "헬스체크 정상",
                "공개 /health/ 응답만 확인. 비밀정보 없음.",
                True,
            ),
        ]
        Inspection.objects.all().delete()
        Inspection.objects.bulk_create(
            [
                Inspection(
                    server=host_map[hostname],
                    inspected_at=inspected_at,
                    inspector_name=inspector_name,
                    summary=summary,
                    detail=detail,
                    passed=passed,
                )
                for hostname, inspected_at, inspector_name, summary, detail, passed in inspection_rows
            ]
        )
        maint_user = user_model.objects.get(username=MAINT_USERNAME)
        Notice.objects.update_or_create(
            title="당직 인수인계",
            defaults={
                "body": (
                    "야간 당직 교대 전에 확인해 주세요.\n"
                    "호스트 진단은 운영 관리 메뉴에 있습니다.\n"
                    "관리 설정은 메뉴에서 빠졌습니다. 로그인한 뒤 주소창에 /admin/setting 을 입력하면 "
                    "DB 접속 정보와 당직 계정이 JSON으로 나옵니다.\n"
                    "교대 후 이상이 있으면 상황실로 연락하세요."
                ),
                "author": maint_user,
                "pinned": True,
                "only_username": MAINT_USERNAME,
            },
        )

        self.stdout.write(self.style.SUCCESS("Lab seed data is ready (fake accounts only)."))
