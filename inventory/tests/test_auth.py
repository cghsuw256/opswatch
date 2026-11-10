from django.core.management import call_command
from django.test import TestCase


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
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/")

    def test_repeated_failures_do_not_lock_account(self):
        for _ in range(8):
            failed = self.client.post("/login/", {"username": "maint", "password": "nope"})
            self.assertEqual(failed.status_code, 200)
        success = self.client.post("/login/", {"username": "maint", "password": "maint123"})
        self.assertEqual(success.status_code, 302)
        self.assertEqual(success["Location"], "/dashboard/")

    def test_logout_requires_post(self):
        self.client.login(username="maint", password="maint123")
        get_response = self.client.get("/logout/")
        self.assertEqual(get_response.status_code, 405)
        post_response = self.client.post("/logout/")
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response["Location"], "/login/")
        blocked = self.client.get("/dashboard/")
        self.assertEqual(blocked.status_code, 302)

    def test_seed_is_idempotent(self):
        call_command("seed_lab", verbosity=0)
        call_command("seed_lab", verbosity=0)
        from django.contrib.auth import get_user_model
        from inventory.models import Employee, Server

        self.assertEqual(get_user_model().objects.filter(username="maint").count(), 1)
        self.assertEqual(Employee.objects.count(), 4)
        self.assertEqual(Server.objects.count(), 3)
