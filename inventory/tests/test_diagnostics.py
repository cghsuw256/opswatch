import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from inventory.services.diagnostics import (
    DiagnosticsBusy,
    DiagnosticsDisabled,
    build_lab_command,
    run_ping_diagnosis,
)


class TokenIssueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def test_issues_static_token_after_login(self):
        self.client.login(username="maint", password="maint123")
        response = self.client.get("/api/internal/token/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["token"], "ow-lab-internal-9f3c2a1b7e44")
        self.assertIsNone(payload["expires_in"])

    def test_frontend_does_not_hardcode_token(self):
        response = self.client.get("/static/opswatch/diagnostics.js")
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertNotIn("ow-lab-internal-9f3c2a1b7e44", body)
        self.assertIn("/api/internal/token/", body)



class DiagnoseApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def test_token_alone_skips_session(self):
        response = self.client.post(
            "/api/internal/diagnose/",
            data=json.dumps({"target": "web-01.lab.local"}),
            content_type="application/json",
            HTTP_X_OPSWATCH_TOKEN="ow-lab-internal-9f3c2a1b7e44",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("실습 컨테이너", response.json()["error"])


    def test_requires_token(self):
        self.client.login(username="maint", password="maint123")
        response = self.client.post(
            "/api/internal/diagnose/",
            data=json.dumps({"target": "web-01.lab.local"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_host_runtime_blocks_shell(self):
        self.client.login(username="maint", password="maint123")
        response = self.client.post(
            "/api/internal/diagnose/",
            data=json.dumps({"token": "ow-lab-internal-9f3c2a1b7e44", "target": "web-01.lab.local"}),
            content_type="application/json",
            HTTP_X_OPSWATCH_TOKEN="ow-lab-internal-9f3c2a1b7e44",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("실습 컨테이너", response.json()["error"])

    def test_invalid_target(self):
        self.client.login(username="maint", password="maint123")
        with override_settings(OPSWATCH_RUNTIME="container", OPSWATCH_ENABLE_DIAGNOSTICS=True):
            response = self.client.post(
                "/api/internal/diagnose/",
                data=json.dumps({"token": "ow-lab-internal-9f3c2a1b7e44", "target": "   "}),
                content_type="application/json",
                HTTP_X_OPSWATCH_TOKEN="ow-lab-internal-9f3c2a1b7e44",
            )
        self.assertEqual(response.status_code, 400)

    def test_successful_diagnosis_is_mocked(self):
        fake = type("R", (), {"status": "ok", "output": "127.0.0.1 web-01.lab.local", "timed_out": False})()
        with patch("inventory.views.run_ping_diagnosis", return_value=fake):
            response = self.client.post(
                "/api/internal/diagnose/",
                data=json.dumps({"token": "ow-lab-internal-9f3c2a1b7e44", "target": "web-01.lab.local"}),
                content_type="application/json",
                HTTP_X_OPSWATCH_TOKEN="ow-lab-internal-9f3c2a1b7e44",
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["output"], "127.0.0.1 web-01.lab.local")


class DiagnoseServiceTests(TestCase):
    def test_host_service_disabled(self):
        with self.assertRaises(DiagnosticsDisabled):
            run_ping_diagnosis("web-01.lab.local")

    def test_command_concatenates_raw_target_without_running_shell(self):
        target = "web-01.lab.local; cat /opt/challenge/flag.txt"
        command = build_lab_command(target)
        self.assertIn(target, command)
        self.assertTrue(command.startswith("/usr/bin/getent hosts "))

    def test_mocked_subprocess_never_executes_real_command(self):
        completed = type("C", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})()
        with override_settings(OPSWATCH_RUNTIME="container", OPSWATCH_ENABLE_DIAGNOSTICS=True):
            with patch("inventory.services.diagnostics.subprocess.run", return_value=completed) as mocked:
                result = run_ping_diagnosis("web-01.lab.local")
        self.assertEqual(result.status, "ok")
        mocked.assert_called_once()
        args, kwargs = mocked.call_args
        self.assertEqual(args[0], "/usr/bin/getent hosts web-01.lab.local")
        self.assertTrue(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 3)

    def test_busy_gate(self):
        from inventory.services import diagnostics as diag

        self.assertTrue(diag._run_gate.acquire(blocking=False))
        try:
            with override_settings(OPSWATCH_RUNTIME="container", OPSWATCH_ENABLE_DIAGNOSTICS=True):
                with self.assertRaises(DiagnosticsBusy):
                    run_ping_diagnosis("web-01.lab.local")
        finally:
            diag._run_gate.release()
