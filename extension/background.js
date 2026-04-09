/**
 * AlienTalk — Background service worker.
 *
 * Bridges content scripts ↔ native messaging host (Rust daemon).
 * Protocol: JSON messages over stdin/stdout via Chrome Native Messaging.
 */

const NATIVE_HOST = "com.alientalk.daemon";

/** @type {chrome.runtime.Port | null} */
let nativePort = null;

/** Pending responses keyed by request ID. */
const pendingRequests = new Map();

/** Reconnection state. */
let reconnectTimer = null;
let reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 30000;

/** Connect to the native messaging host. */
function connectNative() {
  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST);

    // Reset reconnect state on successful connect
    reconnectDelay = 1000;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    nativePort.onMessage.addListener((response) => {
      const { request_id, compressed, savings_pct, error } = response;
      const pending = pendingRequests.get(request_id);
      if (pending) {
        pendingRequests.delete(request_id);
        pending.resolve({ compressed, savings_pct, error });
      }
    });

    nativePort.onDisconnect.addListener(() => {
      const lastError = chrome.runtime.lastError?.message || "unknown";
      console.warn(`[AlienTalk] Native host disconnected: ${lastError}`);
      nativePort = null;

      // Reject all pending requests
      for (const [id, pending] of pendingRequests) {
        pending.resolve({ error: "daemon_disconnected" });
        pendingRequests.delete(id);
      }

      // Schedule reconnection with exponential backoff
      scheduleReconnect();
    });
  } catch (e) {
    console.error("[AlienTalk] Failed to connect native host:", e);
    nativePort = null;
    scheduleReconnect();
  }
}

/** Schedule reconnection with exponential backoff. */
function scheduleReconnect() {
  if (reconnectTimer) return;
  const delay = reconnectDelay;
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    console.log(`[AlienTalk] Reconnecting (delay: ${delay}ms)...`);
    connectNative();
  }, delay);
}

/** Monotonic request ID counter. */
let nextRequestId = 1;

/**
 * Send a compression request to the daemon.
 * @param {string} text - Text to compress.
 * @param {string} url - Source page URL.
 * @returns {Promise<{compressed?: string, savings_pct?: number, error?: string}>}
 */
function sendCompressionRequest(text, url) {
  return new Promise((resolve) => {
    if (!nativePort) {
      connectNative();
    }

    if (!nativePort) {
      resolve({ error: "native_host_unavailable" });
      return;
    }

    const requestId = nextRequestId++;
    pendingRequests.set(requestId, { resolve });

    // Timeout after 3 seconds (generous — daemon should respond in <200ms)
    setTimeout(() => {
      if (pendingRequests.has(requestId)) {
        pendingRequests.delete(requestId);
        resolve({ error: "timeout" });
      }
    }, 3000);

    nativePort.postMessage({
      action: "compress",
      request_id: requestId,
      text,
      url,
    });
  });
}

/**
 * Request stats from the daemon via native messaging.
 * @returns {Promise<{stats?: object, error?: string}>}
 */
function requestStats() {
  return new Promise((resolve) => {
    if (!nativePort) {
      connectNative();
    }

    if (!nativePort) {
      resolve({ error: "native_host_unavailable" });
      return;
    }

    const requestId = nextRequestId++;
    pendingRequests.set(requestId, { resolve });

    setTimeout(() => {
      if (pendingRequests.has(requestId)) {
        pendingRequests.delete(requestId);
        resolve({ error: "timeout" });
      }
    }, 3000);

    nativePort.postMessage({
      action: "get_stats",
      request_id: requestId,
    });
  });
}

// Listen for messages from content scripts and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "compress") {
    sendCompressionRequest(message.text, message.url).then(sendResponse);
    return true; // async response
  }
  if (message.action === "get_stats") {
    requestStats().then(sendResponse);
    return true;
  }
  if (message.action === "get_connection_status") {
    sendResponse({ connected: nativePort !== null });
    return false;
  }
});

// Listen for keyboard shortcut (Cmd+Shift+Enter / Ctrl+Shift+Enter)
chrome.commands.onCommand.addListener((command) => {
  if (command === "optimize") {
    // Forward hotkey to the active tab's content script
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { action: "hotkey_optimize" });
      }
    });
  }
});
