(function () {
  const form = document.getElementById("assistant-form");
  const statusEl = document.getElementById("assistant-status");
  const outputEl = document.getElementById("assistant-output");
  if (!form) return;
  const token = JSON.parse(document.getElementById("assistant-token").textContent);

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!token) {
      statusEl.textContent = "토큰 발급 필요";
      return;
    }
    statusEl.textContent = "확인 중";
    outputEl.hidden = true;
    outputEl.textContent = "";

    const messageInput = form.querySelector('[name="message"]');
    const targetInput = form.querySelector('[name="target"]');
    const csrfInput = form.querySelector('[name="csrfmiddlewaretoken"]');

    try {
      const response = await fetch("/api/internal/assistant/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfInput ? csrfInput.value : "",
          "X-OpsWatch-Token": token,
        },
        body: JSON.stringify({
          message: messageInput.value,
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
      outputEl.textContent = data.reply || "";
    } catch (err) {
      statusEl.textContent = "오류";
      outputEl.hidden = false;
      outputEl.textContent = "네트워크 오류";
    }
  });
})();
