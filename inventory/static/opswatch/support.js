(function () {
  const button = document.getElementById("query-agent-status");
  const statusEl = document.getElementById("agent-status");
  const outputEl = document.getElementById("agent-status-output");
  if (!button) return;

  button.addEventListener("click", async function () {
    button.disabled = true;
    statusEl.textContent = "조회 중";
    outputEl.hidden = true;
    outputEl.textContent = "";
    try {
      const response = await fetch("/api/internal/metadata/", {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
      });
      const data = await response.json();
      if (!response.ok) {
        statusEl.textContent = "오류";
        outputEl.hidden = false;
        outputEl.textContent = data.error || "에이전트 상태를 조회할 수 없습니다.";
        return;
      }
      statusEl.textContent = "조회 완료";
      outputEl.hidden = false;
      outputEl.textContent = "서비스: " + data.service + "\n상태: " + data.status;
    } catch (err) {
      statusEl.textContent = "오류";
      outputEl.hidden = false;
      outputEl.textContent = "네트워크 오류";
    } finally {
      button.disabled = false;
    }
  });
})();
