from django.db import migrations
from django.utils import timezone

HOST = "intranet-01.example.invalid"
CONTACTS = ("duty-nco@example.invalid", "helpdesk@example.invalid")


def add_examples(apps, schema_editor):
    alias = schema_editor.connection.alias
    employee = apps.get_model("inventory", "Employee")
    server = apps.get_model("inventory", "Server")
    inspection = apps.get_model("inventory", "Inspection")
    employee.objects.using(alias).bulk_create([
        employee(email=CONTACTS[0], name="김준호", department="정보통신", title="중사", extension="4500"),
        employee(email=CONTACTS[1], name="박서윤", department="정보통신", title="7급 군무원", extension="4501"),
    ])
    host = server.objects.using(alias).create(
        hostname=HOST, address="192.0.2.10", role="인트라넷", location="교육망",
        cpu_percent=20, memory_percent=40, seed_metrics=False,
    )
    inspection.objects.using(alias).create(
        server=host, inspected_at=timezone.now(), inspector_name="중사 김준호",
        summary="개통 점검 예시", detail="신규 시스템 교육용 예시 기록입니다.",
    )


def remove_examples(apps, schema_editor):
    alias = schema_editor.connection.alias
    apps.get_model("inventory", "Server").objects.using(alias).filter(hostname=HOST).delete()
    apps.get_model("inventory", "Employee").objects.using(alias).filter(email__in=CONTACTS).delete()


class Migration(migrations.Migration):
    dependencies = [("patched_portal", "0001_initial"), ("inventory", "0002_server_diagnostics_permission")]
    operations = [migrations.RunPython(add_examples, remove_examples)]
