(function () {
  const form = document.getElementById("diagnose-form");
  const statusEl = document.getElementById("diag-status");
  const outputEl = document.getElementById("diag-output");
  if (!form) return;
  const tokenEl = document.getElementById("diagnostics-token");
  const token = JSON.parse(tokenEl.textContent);

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!token) {
      statusEl.textContent = "에이전트 상태 조회 필요";
      return;
    }
    statusEl.textContent = "실행 중";
    outputEl.hidden = true;
    outputEl.textContent = "";

    const targetInput = form.querySelector('[name="target"]');
    const csrfInput = form.querySelector('[name="csrfmiddlewaretoken"]');

    try {
      const response = await fetch("/api/internal/diagnose/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfInput ? csrfInput.value : "",
          "X-OpsWatch-Token": token,
        },
        body: JSON.stringify({
          target: targetInput.value,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        statusEl.textContent = "오류";
        outputEl.hidden = false;
        outputEl.textContent = data.error || "요청을 처리할 수 없습니다.";
        return;
      }
      statusEl.textContent = data.status === "ok" ? "완료" : data.status;
      outputEl.hidden = false;
      outputEl.textContent = data.output || "";
    } catch (err) {
      statusEl.textContent = "오류";
      outputEl.hidden = false;
      outputEl.textContent = "네트워크 오류";
    }
  });
})();
