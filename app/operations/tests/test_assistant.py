import json
import subprocess
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from operations.services.diagnostics import _DIAGNOSTIC_SLOT


@override_settings(OPSWATCH_RUNTIME="host", OPSWATCH_ENABLE_DIAGNOSTICS=True)
class AssistantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def setUp(self):
        self.client.login(username="maint", password="maint123")

    def post(self, payload, token=None, client=None):
        return (client or self.client).post(
            "/api/internal/assistant/", json.dumps(payload), content_type="application/json",
            HTTP_X_OPSWATCH_TOKEN=token or "",
        )

    def test_token_only_request_requires_login_without_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        with patch("operations.views.answer_ops_request") as service:
            response = self.post({"message": "확인", "target": "web-01.lab.local; whoami"}, settings.OPSWATCH_INTERNAL_TOKEN, browser)
            self.assertEqual(response.status_code, 401)
            service.assert_not_called()
        self.assertNotIn("_auth_user_id", browser.session)

    def test_api_rejects_missing_or_wrong_token(self):
        with patch("operations.views.answer_ops_request") as service:
            for token in (None, "wrong"):
                self.assertEqual(self.post({"message": "확인", "target": "web-01.lab.local"}, token).status_code, 403)
            service.assert_not_called()

    def test_invalid_payloads(self):
        for payload in ([], None, "text", {"message": []}, {"message": 1},
                        {"message": ""}, {"message": "  "},
                        {"message": "확인", "target": []},
                        {"message": "확인", "target": ""},
                        {"message": "확인", "target": "x" * 201}):
            with self.subTest(payload=payload):
                self.assertEqual(self.post(payload, settings.OPSWATCH_INTERNAL_TOKEN).status_code, 400)
        for body in ("[", b"\xff"):
            self.assertEqual(self.client.post("/api/internal/assistant/", body, content_type="application/json",
                                             HTTP_X_OPSWATCH_TOKEN=settings.OPSWATCH_INTERNAL_TOKEN).status_code, 400)

    @override_settings(OPSWATCH_RUNTIME="container", OPSWATCH_ENABLE_DIAGNOSTICS=True)
    def test_reply_contains_service_output(self):
        with patch("operations.services.diagnostics.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "real command output", "")):
            response = self.post({"message": "확인", "target": "web-01.lab.local; id"}, settings.OPSWATCH_INTERNAL_TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(response.json()["timed_out"])
        self.assertIn("real command output", response.json()["reply"])

    @override_settings(OPSWATCH_RUNTIME="container", OPSWATCH_ENABLE_DIAGNOSTICS=True)
    def test_timeout_and_busy_are_reported(self):
        payload = {"message": "확인", "target": "web-01.lab.local"}
        with patch("operations.services.diagnostics.subprocess.run", side_effect=subprocess.TimeoutExpired("getent", 3, output="partial")):
            response = self.post(payload, settings.OPSWATCH_INTERNAL_TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["timed_out"])
        self.assertIn("partial", response.json()["reply"])
        self.assertTrue(_DIAGNOSTIC_SLOT.acquire(blocking=False))
        try:
            self.assertEqual(self.post(payload, settings.OPSWATCH_INTERNAL_TOKEN).status_code, 429)
        finally:
            _DIAGNOSTIC_SLOT.release()
