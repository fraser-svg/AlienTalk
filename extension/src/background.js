// Sharp background service worker — hotkey handler + Stage 2 request interception.

// ─── Hotkey Handler ──────────────────────────────────────────────

chrome.commands.onCommand.addListener((command) => {
  if (command === "sharpen") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { action: "sharpen" });
      }
    });
  }
});

// ─── Stage 2 Request Interception ────────────────────────────────
//
// Intercepts outbound API calls to AI providers and applies compression
// to message content before it reaches the server.
//
// This is transparent to the user — they see the sharpened (Stage 1) text,
// but the AI receives the compressed (Stage 2) text.
//
// Note: MV3 declarativeNetRequest can't modify request bodies.
// Full Stage 2 interception requires the content script to intercept
// fetch/XHR before the request leaves the page. The background worker
// coordinates this via messaging.

// Store Stage 2 enabled state
let stage2Enabled = false;

chrome.storage.sync.get(["stage2Enabled"], (data) => {
  stage2Enabled = data.stage2Enabled ?? false;
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.stage2Enabled) {
    stage2Enabled = changes.stage2Enabled.newValue;
  }
});

// Message handler for popup/content script queries
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Only handle messages from this extension
  if (sender.id !== chrome.runtime.id) return;

  if (msg.action === "getSettings") {
    chrome.storage.sync.get(["stage2Enabled", "aggressiveness"], (data) => {
      sendResponse({
        stage2Enabled: data.stage2Enabled ?? false,
        aggressiveness: data.aggressiveness ?? "standard",
      });
    });
    return true; // async sendResponse
  }

  if (msg.action === "getStats") {
    chrome.storage.local.get(["promptCount", "tokensSaved"], (data) => {
      sendResponse({
        promptCount: data.promptCount || 0,
        tokensSaved: data.tokensSaved || 0,
      });
    });
    return true;
  }
});

console.log("[Sharp] Background service worker started");
