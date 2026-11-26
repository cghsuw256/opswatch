import json
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase


class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def test_staff_is_public_and_shows_maint_id(self):
        response = self.client.get("/staff/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "maint")
        self.assertContains(response, "박도윤")
        self.assertContains(response, "/static/opswatch/app.css")

    def test_stylesheet_is_served(self):
        response = self.client.get("/static/opswatch/app.css")
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content)
        self.assertIn(b".mast", body)

    def test_health_has_no_secrets(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn('"status": "ok"', body)
        self.assertNotIn("FLAG{", body)
        self.assertNotIn("ow-lab-internal", body)
        self.assertNotIn("maint123", body)

    def test_auth_required_pages_redirect(self):
        for path in ("/dashboard/", "/support/", "/admin/diagnostics/", "/ops/assistant/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/login/", response["Location"])

    def test_metadata_requires_login(self):
        response = self.client.get("/api/internal/metadata/")
        self.assertEqual(response.status_code, 401)

    def test_intranet_home_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])


    def test_authenticated_pages_render(self):
        self.assertTrue(self.client.login(username="maint", password="maint123"))
        dashboard = self.client.get("/dashboard/")
        self.assertContains(dashboard, "web-01.lab.local")
        support = self.client.get("/support/")
        self.assertEqual(support.status_code, 200)
        diagnostics = self.client.get("/admin/diagnostics/")
        self.assertEqual(diagnostics.status_code, 200)
        self.assertEqual(diagnostics.context["diagnostics_token"], "")
        assistant = self.client.get("/ops/assistant/")
        self.assertEqual(assistant.status_code, 200)
        self.assertEqual(assistant.context["diagnostics_token"], "")

    def assert_diagnostics_access(self, allowed):
        for path in ("/admin/diagnostics/", "/ops/assistant/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200 if allowed else 403)
        result = SimpleNamespace(status="ok", output="diagnostic output", timed_out=False)
        for path, service_name, return_value in (
            ("/api/internal/diagnose/", "operations.views.run_ping_diagnosis", result),
            ("/api/internal/assistant/", "operations.views.answer_ops_request", ("reply", result)),
        ):
            with self.subTest(path=path), patch(service_name, return_value=return_value) as service:
                response = self.client.post(
                    path, json.dumps({"target": "web-01.lab.local", "message": "확인"}),
                    content_type="application/json",
                    HTTP_X_OPSWATCH_TOKEN=settings.OPSWATCH_INTERNAL_TOKEN,
                )
                self.assertEqual(response.status_code, 200 if allowed else 403)
                if allowed:
                    service.assert_called_once()
                else:
                    service.assert_not_called()

    def test_regular_users_cannot_execute_even_after_fetching_token(self):
        for username in ("seoyeon", "minjun", "harin"):
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password=username + "123"))
                self.assertEqual(self.client.get("/support/").status_code, 200)
                metadata = self.client.get("/api/internal/metadata/")
                self.assertEqual(metadata.status_code, 200)
                self.assertEqual(
                    metadata.json()["metadata"]["internal_token"],
                    settings.OPSWATCH_INTERNAL_TOKEN,
                )
                self.assert_diagnostics_access(False)

    def test_permission_grant_and_revocation_override_username(self):
        permission = Permission.objects.get(
            content_type__app_label="inventory", codename="run_diagnostics",
        )
        maint = get_user_model().objects.get(username="maint")
        harin = get_user_model().objects.get(username="harin")
        self.client.force_login(maint)
        self.assert_diagnostics_access(True)
        maint.user_permissions.remove(permission)
        self.assert_diagnostics_access(False)
        harin.user_permissions.add(permission)
        self.client.force_login(harin)
        self.assert_diagnostics_access(True)
        harin.user_permissions.remove(permission)
        self.assert_diagnostics_access(False)
