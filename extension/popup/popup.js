// Sharp popup — stats display + settings.

document.addEventListener("DOMContentLoaded", () => {
  // Load stats
  chrome.runtime.sendMessage({ action: "getStats" }, (response) => {
    if (response) {
      document.getElementById("prompt-count").textContent = response.promptCount.toLocaleString();
      document.getElementById("tokens-saved").textContent = response.tokensSaved.toLocaleString();
    }
  });

  // Load settings
  chrome.storage.sync.get(["autoSharpen"], (data) => {
    document.getElementById("auto-sharpen").checked = data.autoSharpen ?? false;
  });

  // Save settings on change
  document.getElementById("auto-sharpen").addEventListener("change", (e) => {
    chrome.storage.sync.set({ autoSharpen: e.target.checked });
  });
});
