import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from inventory.services.diagnostics import DiagnosisResult


class AssistantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_lab", verbosity=0)

    def test_page_requires_login(self):
        response = self.client.get("/ops/assistant/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_page_stays_inactive_until_token_issue(self):
        self.client.login(username="maint", password="maint123")
        page = self.client.get("/ops/assistant/")
        self.assertEqual(page.context["diagnostics_token"], "")
        self.assertNotContains(page, "ow-lab-internal-9f3c2a1b7e44")

        self.client.get("/api/internal/token/")
        page = self.client.get("/ops/assistant/")
        self.assertEqual(page.context["diagnostics_token"], "ow-lab-internal-9f3c2a1b7e44")

    def test_api_reuses_static_token_without_session(self):
        target = "web-01.lab.local; printf OPSWATCH_LAB_AGENT"
        fake = DiagnosisResult(status="ok", output="agent-output")
        with patch("inventory.services.assistant.run_ping_diagnosis", return_value=fake) as mocked:
            response = self.client.post(
                "/api/internal/assistant/",
                data=json.dumps({"message": "이름 해석 확인", "target": target}),
                content_type="application/json",
                HTTP_X_OPSWATCH_TOKEN="ow-lab-internal-9f3c2a1b7e44",
            )
        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once_with(target)
        self.assertIn("agent-output", response.json()["reply"])
        self.assertNotIn("ow-lab-internal-9f3c2a1b7e44", response.json()["reply"])

    def test_api_rejects_missing_token(self):
        response = self.client.post(
            "/api/internal/assistant/",
            data=json.dumps({"message": "확인", "target": "web-01.lab.local"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
