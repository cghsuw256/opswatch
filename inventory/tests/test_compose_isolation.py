from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


class ComposeIsolationTests(SimpleTestCase):
    def test_web_binds_localhost_only(self):
        self.assertIn('"127.0.0.1:8000:8000"', COMPOSE)

    def test_mysql_has_no_host_ports(self):
        db_block = COMPOSE.split("web:")[0]
        self.assertNotIn("ports:", db_block)

    def test_no_privileged_host_network_or_docker_socket(self):
        self.assertNotIn("privileged: true", COMPOSE)
        self.assertNotIn("network_mode: host", COMPOSE)
        self.assertNotIn("docker.sock", COMPOSE)

    def test_no_host_directory_bind_mounts(self):
        self.assertNotIn("./:", COMPOSE)
        self.assertNotIn(".\\", COMPOSE)
        self.assertIn("mysql_data:/var/lib/mysql", COMPOSE)

    def test_lab_network_is_internal(self):
        self.assertIn("internal: true", COMPOSE)

    def test_web_hardening(self):
        self.assertIn("user: \"1000:1000\"", COMPOSE)
        self.assertIn("read_only: true", COMPOSE)
        self.assertIn("no-new-privileges:true", COMPOSE)
        self.assertIn("cap_drop:", COMPOSE)
        self.assertIn("pids_limit: 128", COMPOSE)
        self.assertIn("mem_limit: 512m", COMPOSE)
        self.assertIn("OPSWATCH_RUNTIME: container", COMPOSE)
        self.assertIn("OPSWATCH_ENABLE_DIAGNOSTICS: \"1\"", COMPOSE)

    def test_image_runs_as_nonroot(self):
        self.assertIn("USER appuser", DOCKERFILE)
        self.assertIn("useradd --uid 1000", DOCKERFILE)
        self.assertIn("/opt/challenge/flag.txt", DOCKERFILE)
