"""Diagnostic runner for the OpsWatch lab.

INTENTIONAL EDUCATIONAL VULNERABILITY
-------------------------------------
Location: `run_ping_diagnosis()` command construction.
Cause: unsanitized `target` is interpolated into a shell string and passed to
`subprocess.run(..., shell=True)`.
This path is enabled only inside the lab container. Host/unit tests must mock
subprocess and never execute attacker-controlled commands.
See docs/WALKTHROUGH.md and docs/SECURE_CODING.md.
"""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass

from django.conf import settings

MAX_OUTPUT_BYTES = 8192
TIMEOUT_SECONDS = 3
MAX_TARGET_LEN = 200
_run_gate = threading.BoundedSemaphore(1)


class DiagnosticsDisabled(Exception):
    pass


class DiagnosticsBusy(Exception):
    pass


class DiagnosticsInvalid(Exception):
    pass


@dataclass(frozen=True)
class DiagnosisResult:
    status: str
    output: str
    timed_out: bool = False


def diagnostics_enabled() -> bool:
    return settings.OPSWATCH_RUNTIME == "container" and settings.OPSWATCH_ENABLE_DIAGNOSTICS


def build_lab_command(target: str) -> str:
    """Return the lab command string.

    # INTENTIONAL EDUCATIONAL VULNERABILITY
    # User-controlled `target` is concatenated into a shell command.
    # Do not reuse this helper outside the isolated lab container.
    """
    return f"/usr/bin/getent hosts {target}"


def run_ping_diagnosis(target: str) -> DiagnosisResult:
    if not diagnostics_enabled():
        raise DiagnosticsDisabled("진단 실행은 지정된 실습 컨테이너 안에서만 허용됩니다.")

    cleaned = (target or "").strip()
    if not cleaned:
        raise DiagnosticsInvalid("진단 대상을 입력하세요.")
    if len(cleaned) > MAX_TARGET_LEN:
        raise DiagnosticsInvalid("진단 대상이 너무 깁니다.")

    command = build_lab_command(cleaned)

    if not _run_gate.acquire(blocking=False):
        raise DiagnosticsBusy("다른 진단이 실행 중입니다. 잠시 후 다시 시도하세요.")

    try:
        completed = subprocess.run(
            command,
            shell=True,  # INTENTIONAL EDUCATIONAL VULNERABILITY: shell interpolation
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        merged = (completed.stdout or "") + (completed.stderr or "")
        output = merged[:MAX_OUTPUT_BYTES]
        status = "ok" if completed.returncode == 0 else "error"
        return DiagnosisResult(status=status, output=output or "(출력 없음)")
    except subprocess.TimeoutExpired as exc:
        partial = ""
        if exc.stdout:
            partial += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", "replace")
        if exc.stderr:
            partial += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", "replace")
        return DiagnosisResult(
            status="timeout",
            output=(partial or "진단 시간이 초과되었습니다.")[:MAX_OUTPUT_BYTES],
            timed_out=True,
        )
    finally:
        _run_gate.release()
