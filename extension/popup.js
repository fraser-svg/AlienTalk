/**
 * AlienTalk — Popup script.
 * Displays compression stats from the daemon.
 */

async function loadStats() {
  const statusEl = document.getElementById("status");

  try {
    const response = await chrome.runtime.sendMessage({ action: "get_stats" });

    if (response?.error) {
      statusEl.textContent = "Daemon offline";
      statusEl.className = "status status--offline";
      return;
    }

    if (response?.stats) {
      const { total_compressions, total_saved_tokens, avg_savings_pct } = response.stats;
      document.getElementById("total").textContent = total_compressions.toLocaleString();
      document.getElementById("saved").textContent = total_saved_tokens.toLocaleString();
      document.getElementById("avg").textContent = `${avg_savings_pct.toFixed(1)}%`;
      statusEl.textContent = "Active";
      statusEl.className = "status status--active";
    }
  } catch {
    statusEl.textContent = "Daemon not connected";
    statusEl.className = "status status--offline";
  }
}

loadStats();
