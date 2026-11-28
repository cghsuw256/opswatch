from unittest import skipIf
from unittest.mock import patch


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

    @patch("operations.views.run_posix")
    def test_legacy_diagnostics_runs_shell_command_from_tab(self, run):
        path = "/admin/diagnostics/"
        self.assertRedirects(self.client.get(path), "/login/?next=/admin/diagnostics/")
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(path).status_code, 403)

        client = Client()
        client.force_login(self.maint)
        page = client.get(path)
        self.assertContains(page, 'name="target"')
        self.assertContains(page, "명령 실행")
        run.assert_not_called()

        empty = client.get(path, {"target": ""})
        self.assertContains(empty, "진단 대상을 입력하세요.", status_code=400)
        run.assert_not_called()

        run.return_value.stdout = "reply from localhost\nhan.seoyun@21edu.mil.invalid\n"
        run.return_value.stderr = ""
        run.return_value.returncode = 0
        target = "127.0.0.1; cat /opt/opswatch/data/unit_members.csv"
        result = client.get(path, {"target": target})

        self.assertContains(result, "han.seoyun@21edu.mil.invalid")
        self.assertContains(result, "종료 코드 0")
        self.assertEqual(run.call_args.args[0], f"ping -c 3 {target}")
        self.assertEqual(run.call_args.kwargs["cwd"], settings.BASE_DIR)
        self.assertEqual(run.call_args.kwargs["timeout"], 12)

        run.reset_mock()
        run.side_effect = OSError
        failed = client.get(path, {"target": "127.0.0.1"})
        self.assertContains(failed, "명령을 시작하지 못했습니다.", status_code=500)
        self.assertEqual(self.client.post("/api/internal/diagnose/").status_code, 404)

    def test_legacy_diagnostics_returns_cat_output_without_extra_tools(self):
        client = Client()
        client.force_login(self.maint)
        result = client.get("/admin/diagnostics/", {"target": "127.0.0.1; cat /opt/opswatch/data/unit_members.csv"})
        self.assertContains(result, "han.seoyun@21edu.mil.invalid")
        self.assertContains(result, "ping -c 3 127.0.0.1; cat /opt/opswatch/data/unit_members.csv")
        self.assertNotContains(result, "wsl")
        self.assertNotContains(result, "u.csv")
        self.assertNotContains(result, "sh.exe")
