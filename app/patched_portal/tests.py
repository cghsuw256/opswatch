from datetime import timedelta
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from operations.models import Employee, Inspection, Server


@skipUnless(getattr(settings, "PATCHED_SITE", False), "requires config.patched")
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PatchedSiteTests(TestCase):
    password = "Unique-range-43-to-provision"

    @classmethod
    def setUpTestData(cls):
        cls.operator = get_user_model().objects.create_user("operator_a", password=cls.password)
        cls.reader = get_user_model().objects.create_user("reader_a")
        cls.operator.user_permissions.add(Permission.objects.get(
            content_type__app_label="inventory", codename="run_diagnostics",
        ))

    def test_legacy_paths_absent_even_with_session(self):
        self.client.force_login(self.operator)
        for path in ("/dev/setting", "/api/internal/metadata/", "/api/internal/diagnose/",
                     "/ops/assistant/", "/api/internal/assistant/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
                self.assertEqual(self.client.post(path).status_code, 404)

    def test_settings_exposes_only_database_engine_to_portal_admin(self):
        path = "/admin/setting"
        self.assertRedirects(self.client.get(path), "/login/?next=/admin/setting")
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(path).status_code, 403)
        profile = self.operator.profile
        profile.role = "admin"
        profile.save(update_fields=["role"])
        response = self.client.get(path)
        self.assertEqual(response.json(), {"database": {"engine": "sqlite3"}})
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post(path).status_code, 405)

    def test_public_directory_keeps_rank_but_not_authentication_fields(self):
        Employee.objects.create(name="정지훈", department="운영", title="중사", extension="4511",
                                login_id="private-user-id", duty="private staff note",
                                email="private-contact@example.invalid")
        response = self.client.get("/staff/")
        self.assertContains(response, "계급·직급")
        self.assertContains(response, "중사")
        self.assertContains(response, "7급 군무원")
        for value in ("private-user-id", "private staff note", "private-contact@example.invalid", "콘솔 ID"):
            self.assertNotContains(response, value)

    @patch("patched_portal.views.time", return_value=125)
    def test_login_limit_applies_across_accounts_and_expires(self, clock):
        for attempt in range(10):
            response = self.client.post("/login/", {"username": f"unknown{attempt}", "password": "bad"},
                                        HTTP_X_FORWARDED_FOR=f"192.0.2.{attempt + 1}")
            self.assertContains(response, "올바르지 않습니다")
        credentials = {"username": self.operator.username, "password": self.password}
        blocked = Client().post("/login/", credentials)
        self.assertContains(blocked, "시도가 너무 많습니다", status_code=429)
        self.assertEqual(blocked["Retry-After"], "55")
        clock.return_value = 180
        response = self.client.post("/login/", credentials)
        self.assertRedirects(response, "/")
        self.assertIn("intranet_session", response.cookies)
        self.assertNotIn("sessionid", response.cookies)

    def test_diagnostics_requires_session_permission_and_csrf(self):
        path = "/admin/diagnostics/"
        self.assertRedirects(self.client.get(path), "/login/?next=/admin/diagnostics/")
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(path).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.operator)
        page = client.get(path)
        token = page.cookies["intranet_csrf"].value
        self.assertEqual(client.post(path, {"server": 1}).status_code, 403)
        invalid = client.post(path, {"server": 999999, "csrfmiddlewaretoken": token})
        self.assertEqual(invalid.status_code, 400)
        self.assertTrue(invalid.context["form"].has_error("server", "invalid_choice"))

        host = Server.objects.create(hostname="lookup.example.invalid", cpu_percent=0, memory_percent=0)
        now = timezone.now()
        Inspection.objects.create(server=host, inspected_at=now - timedelta(hours=1), summary="이전 기록")
        Inspection.objects.create(server=host, inspected_at=now, summary="최신 기록", detail="<b>기록 내용</b>")
        result = client.post(path, {"server": host.pk, "csrfmiddlewaretoken": token})
        self.assertContains(result, host.hostname)
        self.assertContains(result, "최신 기록")
        self.assertContains(result, "&lt;b&gt;기록 내용&lt;/b&gt;")
        self.assertNotContains(result, "이전 기록")

    def test_create_operator_enforces_policy_and_displays_civilian_grade(self):
        args = ("supporter", "--name", "최보라", "--rank", "8급 군무원", "--diagnostics")
        with patch("patched_portal.management.commands.create_operator.getpass", return_value="12345678"):
            with self.assertRaises(CommandError):
                call_command("create_operator", *args, stdout=StringIO())
        self.assertFalse(get_user_model().objects.filter(username="supporter").exists())
        with patch("patched_portal.management.commands.create_operator.getpass", return_value=self.password):
            call_command("create_operator", *args, stdout=StringIO())
        response = self.client.post("/login/", {"username": "supporter", "password": self.password}, follow=True)
        self.assertContains(response, "8급 군무원 최보라")
        self.assertContains(self.client.get("/people/", {"q": "군무원"}), "최보라")
        self.assertEqual(self.client.get("/admin/diagnostics/").status_code, 200)
