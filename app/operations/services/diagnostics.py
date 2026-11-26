"""Intentionally vulnerable shell diagnostics, restricted to the isolated container."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from threading import BoundedSemaphore

from django.conf import settings
from django.utils import timezone

from operations.models import Server

MAX_TARGET_LEN = 200
MAX_OUTPUT_LEN = 8192
_DIAGNOSTIC_SLOT = BoundedSemaphore(1)


class DiagnosticsInvalid(Exception):
    pass


class DiagnosticsDisabled(Exception):
    pass


class DiagnosticsBusy(Exception):
    pass


@dataclass(frozen=True)
class DiagnosisResult:
    status: str
    output: str
    timed_out: bool = False


def diagnostics_enabled() -> bool:
    return settings.OPSWATCH_RUNTIME == "container" and settings.OPSWATCH_ENABLE_DIAGNOSTICS


def _target_text(target: str) -> str:
    if not isinstance(target, str) or not target.strip():
        raise DiagnosticsInvalid("진단 대상을 문자열로 입력하세요.")
    if len(target) > MAX_TARGET_LEN or "\x00" in target:
        raise DiagnosticsInvalid("진단 대상은 NUL 문자 없이 200자 이하여야 합니다.")
    return target.strip()


def format_host_report(hostname: str) -> str:
    server = Server.objects.filter(hostname=hostname).first()
    if server is None:
        return f"대상: {hostname}\n판정: 등록되지 않은 호스트"
    lines = [
        "검사 항목: 저장된 호스트 상태",
        f"호스트: {server.hostname}",
        f"주소: {server.address}",
        f"역할: {server.role}",
        f"상태: {server.get_status_display()}",
        f"CPU 점유율: {server.cpu_percent}%",
        f"메모리 점유율: {server.memory_percent}%",
        "최근 점검 로그:",
    ]
    rows = list(server.inspections.all()[:5])
    if not rows:
        lines.append("- 기록 없음")
    for row in rows:
        when = timezone.localtime(row.inspected_at).strftime("%Y-%m-%d %H:%M")
        result = "통과" if row.passed else "실패"
        lines.extend([
            f"- {when} {row.inspector_name} / {row.summary} / {result}",
            f"  {row.detail}",
        ])
    return "\n".join(lines)


def _text(output: str | bytes | None) -> str:
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output or ""


def run_ping_diagnosis(target: str) -> DiagnosisResult:
    cleaned = _target_text(target)
    if not diagnostics_enabled():
        raise DiagnosticsDisabled("진단은 활성화된 격리 컨테이너에서만 실행할 수 있습니다.")
    if not _DIAGNOSTIC_SLOT.acquire(blocking=False):
        raise DiagnosticsBusy("다른 진단이 실행 중입니다. 잠시 후 다시 시도하세요.")
    try:
        timed_out = False
        try:
            # INTENTIONAL LAB WEAKNESS: untrusted target is concatenated into a shell command.
            completed = subprocess.run(
                f"/usr/bin/getent hosts {cleaned}",
                shell=True, capture_output=True, text=True, timeout=3,
            )
            status = "ok" if completed.returncode == 0 else "error"
            command_output = _text(completed.stdout) + _text(completed.stderr)
        except subprocess.TimeoutExpired as exc:
            status = "error"
            timed_out = True
            command_output = _text(exc.stdout) + _text(exc.stderr)
        hostname = re.split(r";|&&", cleaned, maxsplit=1)[0].strip()
        output = format_host_report(hostname) + "\n\n추가 명령 출력:\n" + command_output
        return DiagnosisResult(status, output.encode("utf-8")[:MAX_OUTPUT_LEN].decode("utf-8", errors="ignore"), timed_out)
    finally:
        _DIAGNOSTIC_SLOT.release()
