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
        self.assertIn(b".lab-banner", body)

    def test_health_has_no_secrets(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn('"status": "ok"', body)
        self.assertNotIn("FLAG{", body)
        self.assertNotIn("ow-lab-internal", body)
        self.assertNotIn("maint123", body)

    def test_auth_required_pages_redirect(self):
        for path in ("/dashboard/", "/support/", "/admin/diagnostics/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/login/", response["Location"])

    def test_support_script_requires_login(self):
        response = self.client.get("/support/scripts/healthcheck.sh")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_authenticated_pages_render(self):
        self.assertTrue(self.client.login(username="maint", password="maint123"))
        dashboard = self.client.get("/dashboard/")
        self.assertContains(dashboard, "시드된 모의 데이터")
        self.assertContains(dashboard, "web-01.lab.local")
        self.assertContains(dashboard, "알림 추이")
        self.assertContains(dashboard, "<polyline")
        self.assertNotContains(dashboard, "rack.svg")
        support = self.client.get("/support/")
        self.assertEqual(support.status_code, 200)
        diagnostics = self.client.get("/admin/diagnostics/")
        self.assertEqual(diagnostics.status_code, 200)
        self.assertContains(diagnostics, "Django 관리자 사이트 아님")
