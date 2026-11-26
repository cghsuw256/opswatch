(function () {
  const state = document.getElementById("metrics-state");
  const updated = document.getElementById("metrics-updated");
  const rows = Array.from(document.querySelectorAll('tr[data-simulated="true"]'));
  if (!rows.length) return;

  const metrics = rows.flatMap(function (row) {
    return ["cpu", "memory"].map(function (kind) {
      const value = row.querySelector('[data-metric-value="' + kind + '"]');
      const bar = row.querySelector('[data-metric-bar="' + kind + '"]');
      return {
        value: value,
        bar: bar,
        base: parseFloat(value.textContent),
        phase: Number(row.dataset.serverId) * 0.83 + (kind === "memory" ? 2 : 0),
        amplitude: kind === "cpu" ? 14 : 6,
        speed: kind === "cpu" ? 0.9 : 0.4,
      };
    });
  });
  const started = Date.now();
  let timer = null;

  function update() {
    const tick = (Date.now() - started) / 3000;
    metrics.forEach(function (metric) {
      const wave = (Math.sin(tick * metric.speed + metric.phase) - Math.sin(metric.phase)) / 2;
      const value = Math.max(0, Math.min(100, metric.base + metric.amplitude * wave)).toFixed(1);
      metric.bar.style.width = value + "%";
      metric.bar.parentElement.setAttribute("aria-valuenow", value);
      metric.value.textContent = value + "%";
    });
    const now = new Date();
    updated.dateTime = now.toISOString();
    updated.textContent = now.toLocaleTimeString("ko-KR", { hour12: false });
  }

  function stop() {
    window.clearInterval(timer);
    timer = null;
  }

  function resume() {
    stop();
    if (document.hidden) {
      state.textContent = "실습 시뮬레이션 · 일시정지";
      return;
    }
    state.textContent = "실습 시뮬레이션 · 3초 갱신";
    update();
    timer = window.setInterval(update, 3000);
  }

  document.addEventListener("visibilitychange", resume);
  window.addEventListener("pagehide", stop);
  window.addEventListener("pageshow", resume);
  resume();
})();
