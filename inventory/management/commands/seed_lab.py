from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import Employee, Inspection, Server

# Fake lab credentials. Not production values.
MAINT_USERNAME = "maint"
MAINT_PASSWORD = "maint123"


class Command(BaseCommand):
    help = "Idempotently seed fake employees, the weak maintenance user, servers, and inspections."

    def handle(self, *args, **options):
        user_model = get_user_model()
        user, _created = user_model.objects.update_or_create(
            username=MAINT_USERNAME,
            defaults={
                "is_staff": False,
                "is_superuser": False,
                "email": "maint@opswatch.lab",
                "first_name": "도윤",
                "last_name": "박",
            },
        )
        user.set_password(MAINT_PASSWORD)
        user.save()

        employees = [
            {
                "email": "seoyeon.kim@opswatch.lab",
                "name": "김서연",
                "department": "인사총무",
                "title": "사원",
                "login_id": "",
                "extension": "4102",
                "duty": "사내 공지 및 계정 신청 안내",
            },
            {
                "email": "minjun.lee@opswatch.lab",
                "name": "이민준",
                "department": "인프라운영",
                "title": "선임",
                "login_id": "",
                "extension": "4307",
                "duty": "가상 서버 점검 일정 조율",
            },
            {
                "email": "doyun.park@opswatch.lab",
                "name": "박도윤",
                "department": "야간유지보수",
                "title": "유지보수 담당",
                "login_id": MAINT_USERNAME,
                "extension": "4501",
                "duty": "야간 장애 접수. 콘솔 로그인 ID는 내선 안내와 동일합니다.",
            },
            {
                "email": "harin.choi@opswatch.lab",
                "name": "최하린",
                "department": "모니터링",
                "title": "사원",
                "login_id": "",
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

        self.stdout.write(self.style.SUCCESS("Lab seed data is ready (fake accounts only)."))
