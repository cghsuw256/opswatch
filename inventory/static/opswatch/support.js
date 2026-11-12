(function () {
  const button = document.getElementById("issue-token");
  const statusEl = document.getElementById("token-status");
  const outputEl = document.getElementById("token-output");
  if (!button) return;

  button.addEventListener("click", async function () {
    statusEl.textContent = "발급 중";
    outputEl.hidden = true;
    outputEl.textContent = "";
    try {
      const response = await fetch("/api/internal/token/", {
        method: "GET",
        credentials: "same-origin",
      });
      const data = await response.json();
      if (!response.ok) {
        statusEl.textContent = "오류";
        outputEl.hidden = false;
        outputEl.textContent = data.error || "토큰을 발급할 수 없습니다.";
        return;
      }
      statusEl.textContent = "발급됨";
      outputEl.hidden = false;
      outputEl.textContent = data.token || "";
    } catch (err) {
      statusEl.textContent = "오류";
      outputEl.hidden = false;
      outputEl.textContent = "네트워크 오류";
    }
  });
})();
