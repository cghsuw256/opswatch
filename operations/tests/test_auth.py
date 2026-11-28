from unittest import skipIf

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from operations.models import Employee


@skipIf(getattr(settings, "PATCHED_SITE", False), "requires config.settings")
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def test_login_failure_message(self):
        response = self.client.post("/login/", {"username": "maint", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "계정 또는 비밀번호가 올바르지 않습니다.")

    def test_login_success(self):
        response = self.client.post("/login/", {"username": "maint", "password": "maint123"})
        self.assertRedirects(response, "/")

    def test_repeated_failures_do_not_lock_account(self):
        for _ in range(8):
            failed = self.client.post("/login/", {"username": "maint", "password": "nope"})
            self.assertEqual(failed.status_code, 200)
        success = self.client.post("/login/", {"username": "maint", "password": "maint123"})
        self.assertEqual(success.status_code, 302)
        self.assertEqual(success["Location"], "/")

    def test_logout_requires_post(self):
        self.client.login(username="maint", password="maint123")
        get_response = self.client.get("/logout/")
        self.assertEqual(get_response.status_code, 405)
        post_response = self.client.post("/logout/")
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response["Location"], "/login/")
        self.assertRedirects(self.client.get("/"), "/login/?next=/")

    def test_seed_is_idempotent(self):
        call_command("seed_lab", verbosity=0)
        user = get_user_model().objects.get(username="maint")
        self.assertTrue(user.check_password("maint123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.has_perm("inventory.run_diagnostics"))
        self.assertEqual(Employee.objects.filter(login_id="maint").count(), 1)
