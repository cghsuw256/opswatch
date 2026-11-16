"""Situation-room assistant for the OpsWatch lab.

The assistant does not build a shell command. It forwards the operator-supplied
target to the existing diagnosis service, which remains the command-construction
boundary.
"""

from __future__ import annotations

from inventory.services.diagnostics import DiagnosisResult, run_ping_diagnosis


def answer_ops_request(message: str, target: str) -> tuple[str, DiagnosisResult]:
    result = run_ping_diagnosis(target)
    reply = (
        "상황실 보조 에이전트가 내부 진단 API에 호스트 상태 점검을 요청했습니다.\n"
        f"요청: {message.strip()}\n"
        f"대상: {target.strip()}\n"
        f"상태: {result.status}\n\n"
        f"{result.output}"
    )
    return reply, result
