import json
import subprocess
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from operations.services.diagnostics import (
    DiagnosticsBusy, DiagnosticsDisabled, DiagnosticsInvalid,
    MAX_OUTPUT_LEN, _DIAGNOSTIC_SLOT, run_ping_diagnosis,
)


class MetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def test_metadata_activates_only_current_session(self):
        self.client.login(username="maint", password="maint123")
        self.assertEqual(self.client.get("/admin/diagnostics/").context["diagnostics_token"], "")
        response = self.client.get("/api/internal/metadata/")
        self.assertEqual(response.json(), {
            "service": "opswatch-agent", "status": "ok",
            "metadata": {"internal_token": settings.OPSWATCH_INTERNAL_TOKEN,
                         "authentication": "static-token", "expires_in": None},
        })
        self.assertIn("no-store", response["Cache-Control"])
        for path in ("/admin/diagnostics/", "/ops/assistant/"):
            self.assertEqual(self.client.get(path).context["diagnostics_token"], settings.OPSWATCH_INTERNAL_TOKEN)
        other = Client()
        other.login(username="harin", password="harin123")
        self.assertEqual(other.get("/admin/diagnostics/").status_code, 403)
        self.assertEqual(other.get("/api/internal/metadata/").json(), response.json())
        self.client.post("/logout/")
        self.client.login(username="maint", password="maint123")
        self.assertEqual(self.client.get("/admin/diagnostics/").context["diagnostics_token"], "")

    def test_page_runtime_context_uses_both_gates(self):
        self.client.login(username="maint", password="maint123")
        for runtime, enabled in (("host", True), ("container", False), ("container", True)):
            with override_settings(OPSWATCH_RUNTIME=runtime, OPSWATCH_ENABLE_DIAGNOSTICS=enabled):
                for path in ("/admin/diagnostics/", "/ops/assistant/"):
                    self.assertEqual(self.client.get(path).context["diagnostics_enabled"], runtime == "container" and enabled)


@override_settings(OPSWATCH_RUNTIME="host", OPSWATCH_ENABLE_DIAGNOSTICS=True)
class DiagnoseApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def setUp(self):
        self.client.login(username="maint", password="maint123")

    def post_target(self, target, token=None, client=None):
        return (client or self.client).post(
            "/api/internal/diagnose/", json.dumps({"target": target}),
            content_type="application/json", HTTP_X_OPSWATCH_TOKEN=token or "",
        )

    def test_token_only_request_requires_login_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        with patch("operations.views.run_ping_diagnosis") as service:
            response = self.post_target("web-01.lab.local; whoami", settings.OPSWATCH_INTERNAL_TOKEN, client)
            self.assertEqual(response.status_code, 401)
            self.assertIn("error", response.json())
            service.assert_not_called()
        self.assertNotIn("_auth_user_id", client.session)

    def test_missing_and_wrong_tokens_rejected_before_service(self):
        with patch("operations.views.run_ping_diagnosis") as service:
            for token in (None, "wrong"):
                self.assertEqual(self.post_target("web-01.lab.local", token).status_code, 403)
            service.assert_not_called()

    def test_invalid_targets_rejected(self):
        for target in ("", "   ", "a" * 201, [], {}, 123, None, "a\u0000b"):
            with self.subTest(target=target):
                self.assertEqual(self.post_target(target, settings.OPSWATCH_INTERNAL_TOKEN).status_code, 400)

    def test_malformed_json_and_non_object_roots_rejected(self):
        for body in ("[", "[]", "null", '"text"', "1", b"\xff"):
            with self.subTest(body=body):
                response = self.client.post("/api/internal/diagnose/", body, content_type="application/json",
                                            HTTP_X_OPSWATCH_TOKEN=settings.OPSWATCH_INTERNAL_TOKEN)
                self.assertEqual(response.status_code, 400)

    @override_settings(OPSWATCH_RUNTIME="container", OPSWATCH_ENABLE_DIAGNOSTICS=True)
    def test_api_returns_actual_service_result_and_busy_status(self):
        with patch("operations.services.diagnostics.subprocess.run", return_value=subprocess.CompletedProcess([], 7, "actual stdout", "actual stderr")):
            response = self.post_target("unknown; id", settings.OPSWATCH_INTERNAL_TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertFalse(response.json()["timed_out"])
        self.assertIn("actual stdoutactual stderr", response.json()["output"])
        self.assertTrue(_DIAGNOSTIC_SLOT.acquire(blocking=False))
        try:
            self.assertEqual(self.post_target("web-01.lab.local", settings.OPSWATCH_INTERNAL_TOKEN).status_code, 429)
        finally:
            _DIAGNOSTIC_SLOT.release()


@override_settings(OPSWATCH_RUNTIME="container", OPSWATCH_ENABLE_DIAGNOSTICS=True)
class DiagnoseServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def test_real_shell_command_and_saved_report(self):
        for target in ("web-01.lab.local; whoami", "web-01.lab.local && id"):
            with self.subTest(target=target), patch("operations.services.diagnostics.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "command result", "")):
                result = run_ping_diagnosis(target)
                self.assertEqual(result.status, "ok")
                self.assertIn("23%", result.output)
                self.assertIn("41%", result.output)
                self.assertIn("TLS 인증서 만료일 확인", result.output)
                self.assertIn("command result", result.output)

    def test_host_or_disabled_container_never_starts_process(self):
        for runtime, enabled in (("host", True), ("host", False), ("container", False)):
            with self.subTest(runtime=runtime, enabled=enabled), override_settings(OPSWATCH_RUNTIME=runtime, OPSWATCH_ENABLE_DIAGNOSTICS=enabled), patch("operations.services.diagnostics.subprocess.run") as process:
                with self.assertRaises(DiagnosticsDisabled):
                    run_ping_diagnosis("web-01.lab.local; id")
                process.assert_not_called()

    def test_invalid_targets_never_start_process(self):
        with patch("operations.services.diagnostics.subprocess.run") as process:
            for target in (None, 1, [], {}, "", " ", "x" * 201, "x\u0000y"):
                with self.subTest(target=target), self.assertRaises(DiagnosticsInvalid):
                    run_ping_diagnosis(target)
            process.assert_not_called()

    def test_timeout_keeps_partial_output_and_releases_slot(self):
        with patch("operations.services.diagnostics.subprocess.run", side_effect=subprocess.TimeoutExpired("getent", 3, output=b"partial output", stderr=b"partial error")):
            result = run_ping_diagnosis("web-01.lab.local")
        self.assertTrue(result.timed_out)
        self.assertEqual(result.status, "error")
        self.assertIn("partial outputpartial error", result.output)
        self.assertTrue(_DIAGNOSTIC_SLOT.acquire(blocking=False))
        _DIAGNOSTIC_SLOT.release()

    def test_busy_never_starts_second_process(self):
        self.assertTrue(_DIAGNOSTIC_SLOT.acquire(blocking=False))
        try:
            with patch("operations.services.diagnostics.subprocess.run") as process:
                with self.assertRaises(DiagnosticsBusy):
                    run_ping_diagnosis("web-01.lab.local")
                process.assert_not_called()
        finally:
            _DIAGNOSTIC_SLOT.release()

    def test_output_is_bounded(self):
        with patch("operations.services.diagnostics.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "x" * 20000, "")):
            self.assertEqual(len(run_ping_diagnosis("web-01.lab.local").output.encode("utf-8")), MAX_OUTPUT_LEN)
