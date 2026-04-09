/**
 * AlienTalk — Popup script.
 * Displays compression stats from the daemon.
 * Shows onboarding state when daemon is not connected.
 */

async function loadStats() {
  const statusEl = document.getElementById("status");
  const onboardingEl = document.getElementById("onboarding");
  const statsSection = document.getElementById("stats-section");

  try {
    const response = await chrome.runtime.sendMessage({ action: "get_stats" });

    if (response?.error) {
      showOffline(statusEl, onboardingEl, statsSection);
      return;
    }

    if (response?.stats) {
      const { total_compressions, total_saved_tokens, avg_savings_pct } = response.stats;

      if (total_compressions === 0) {
        // First-time user: show stats at zero but with active status
        document.getElementById("total").textContent = "0";
        document.getElementById("saved").textContent = "0";
        document.getElementById("avg").textContent = "-";
      } else {
        document.getElementById("total").textContent = total_compressions.toLocaleString();
        document.getElementById("saved").textContent = total_saved_tokens.toLocaleString();
        document.getElementById("avg").textContent = `${avg_savings_pct.toFixed(1)}%`;
      }

      statusEl.textContent = "Active";
      statusEl.className = "status status--active";
      onboardingEl.style.display = "none";
      statsSection.style.display = "block";
    }
  } catch {
    showOffline(statusEl, onboardingEl, statsSection);
  }
}

function showOffline(statusEl, onboardingEl, statsSection) {
  statusEl.textContent = "Daemon offline";
  statusEl.className = "status status--offline";
  onboardingEl.style.display = "block";
  statsSection.style.display = "none";
}

loadStats();
