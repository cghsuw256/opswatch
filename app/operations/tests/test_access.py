from unittest import skipIf

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings


@skipIf(getattr(settings, "PATCHED_SITE", False), "requires config.settings")
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)
        cls.maint = get_user_model().objects.get(username="maint")
        cls.reader = get_user_model().objects.create_user("reader")

    def test_staff_is_public_and_shows_maint_id(self):
        response = self.client.get("/staff/")
        self.assertContains(response, "maint")
        self.assertContains(response, "박도윤")

    def test_settings_fixture_is_public_and_marked_as_an_example(self):
        response = self.client.get("/admin/setting")
        self.assertEqual(response.status_code, 200)
        fixture = response.json()
        self.assertTrue(fixture["example_only"])
        self.assertTrue(fixture["database"]["host"].endswith(".invalid"))
        self.assertIn("password", fixture["database"])

    def test_handover_notice_is_only_visible_to_the_maintenance_account(self):
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get("/notices/"), "당직 인수인계")
        self.client.force_login(self.maint)
        page = self.client.get("/notices/")
        self.assertContains(page, "당직 인수인계")
        notice = page.context["notices"].get(title="당직 인수인계")
        self.assertContains(self.client.get(f"/notices/{notice.pk}/"), "/admin/setting")

    def test_legacy_diagnostics_redirects_only_after_authorized_submission(self):
        path = "/admin/diagnostics/"
        self.assertRedirects(self.client.get(path), "/login/?next=/admin/diagnostics/")
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(path).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.maint)
        page = client.get(path)
        self.assertContains(page, "패치 사이트로 이동합니다")
        self.assertEqual(client.post(path).status_code, 403)
        response = client.post(path, {"csrfmiddlewaretoken": page.cookies["csrftoken"].value})
        self.assertRedirects(response, "http://127.0.0.1:8001/", fetch_redirect_response=False)
        self.assertEqual(self.client.post("/api/internal/diagnose/").status_code, 404)
