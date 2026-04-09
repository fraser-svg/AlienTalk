/**
 * AlienTalk — Content script.
 *
 * Injects an "Optimize" button near AI chat input fields.
 * Tracks last-focused editable element (avoids focus-steal on button click).
 * Per-element-type write-back strategy:
 *   - textarea/input: native setter + InputEvent dispatch (React-safe)
 *   - contenteditable: InputEvent with insertText (ProseMirror-safe)
 *   - fallback: copy to clipboard + notification
 */

/** Last-focused editable element. Captured via focusin so button click
 *  doesn't lose track of the text field. */
let lastEditableEl = null;

/** Undo state: stores original text per element for one-step undo. */
const undoMap = new WeakMap();

/** Compression in progress flag (debounce guard). */
let isCompressing = false;

/** Track editable element focus. */
document.addEventListener("focusin", (e) => {
  const t = e.target;
  if (
    t instanceof HTMLTextAreaElement ||
    t instanceof HTMLInputElement ||
    t.isContentEditable
  ) {
    lastEditableEl = t;
  }
}, true);

/** Check if we're on a supported site. */
function getSiteName() {
  const host = location.hostname;
  if (host === "claude.ai" || host.endsWith(".claude.ai")) return "claude";
  if (host === "chatgpt.com" || host.endsWith(".chatgpt.com")) return "chatgpt";
  if (host === "gemini.google.com" || host.endsWith(".gemini.google.com")) return "gemini";
  return null;
}

/**
 * Get site-specific button position offsets.
 * @param {string} site
 * @returns {{bottom: string, right: string}}
 */
function getButtonPosition(site) {
  switch (site) {
    case "chatgpt":
      return { bottom: "100px", right: "80px" };
    case "gemini":
      return { bottom: "90px", right: "30px" };
    case "claude":
    default:
      return { bottom: "80px", right: "20px" };
  }
}

/**
 * Map daemon error codes to human-readable messages.
 * @param {string} errorCode
 * @returns {string}
 */
function humanError(errorCode) {
  switch (errorCode) {
    case "daemon_disconnected":
      return "AlienTalk daemon is offline. Check the menu bar icon.";
    case "native_host_unavailable":
      return "AlienTalk daemon not found. Install it from the popup menu.";
    case "timeout":
      return "Optimization timed out. Try a shorter prompt.";
    default:
      return `Error: ${errorCode}`;
  }
}

/**
 * Read text from an element.
 * @param {HTMLElement} el
 * @returns {string}
 */
function readText(el) {
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
    return el.value;
  }
  if (el.isContentEditable) {
    return el.innerText || "";
  }
  return "";
}

/**
 * Write text back to an element, using the appropriate strategy.
 * @param {HTMLElement} el
 * @param {string} text
 * @returns {boolean} true if write succeeded
 */
function writeText(el, text) {
  // Strategy 1: textarea/input — set .value + dispatch InputEvent
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
    // Use native setter to bypass React's synthetic event system
    const nativeSetter = Object.getOwnPropertyDescriptor(
      el instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype,
      "value"
    )?.set;

    if (nativeSetter) {
      nativeSetter.call(el, text);
    } else {
      el.value = text;
    }

    // Dispatch events that React/Vue/Angular listen for
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  // Strategy 2: contenteditable — select all + synthetic InputEvent
  // Works with ProseMirror (claude.ai, chatgpt.com) and Lit editors (gemini).
  if (el.isContentEditable) {
    el.focus();

    // Select all content
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    selection?.removeAllRanges();
    selection?.addRange(range);

    // Try multiple write strategies in order of preference.
    // ProseMirror (claude.ai, chatgpt.com) and Lit editors (gemini) each
    // handle different event types.

    // Strategy A: Synthetic paste via DataTransfer.
    // ProseMirror handles paste events reliably, updating its internal state.
    const dt = new DataTransfer();
    dt.setData("text/plain", text);
    const pasteEvent = new ClipboardEvent("paste", {
      clipboardData: dt,
      bubbles: true,
      cancelable: true,
    });
    const pasteHandled = !el.dispatchEvent(pasteEvent);
    // dispatchEvent returns false when preventDefault() was called,
    // meaning the framework handled the paste.

    if (!pasteHandled) {
      // Strategy B: beforeinput event for editors that handle InputEvents.
      const beforeInput = new InputEvent("beforeinput", {
        inputType: "insertReplacementText",
        data: text,
        bubbles: true,
        cancelable: true,
        composed: true,
      });
      const inputHandled = !el.dispatchEvent(beforeInput);

      if (!inputHandled) {
        // Strategy C: Direct textContent set (loses undo, last resort).
        el.textContent = text;
      }
    }

    // Fire input event for any remaining listeners
    el.dispatchEvent(new InputEvent("input", {
      inputType: "insertText",
      data: text,
      bubbles: true,
    }));

    return true;
  }

  // Strategy 3: clipboard fallback
  return false;
}

/**
 * Copy text to clipboard as a fallback.
 * @param {string} text
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showNotification("Copied to clipboard (couldn't write directly)");
  } catch {
    showNotification("Compression failed — couldn't write or copy");
  }
}

/**
 * Show a brief notification near the active element.
 * @param {string} message
 * @param {number} [savingsPct]
 * @param {boolean} [showUndo] - Show undo link in the notification
 */
function showNotification(message, savingsPct, showUndo = false, undoTarget = null) {
  const existing = document.querySelector(".alientalk-notification");
  if (existing) existing.remove();

  const el = document.createElement("div");
  el.className = "alientalk-notification";
  el.setAttribute("role", "status");
  el.setAttribute("aria-live", "polite");

  const textSpan = document.createElement("span");
  textSpan.textContent = savingsPct != null
    ? `${savingsPct.toFixed(0)}% faster response`
    : message;
  el.appendChild(textSpan);

  if (showUndo && undoTarget) {
    const undoLink = document.createElement("button");
    undoLink.className = "alientalk-undo";
    undoLink.textContent = "Undo";
    undoLink.setAttribute("aria-label", "Undo optimization");
    undoLink.addEventListener("click", (e) => {
      e.stopPropagation();
      performUndo(undoTarget);
      el.remove();
    });
    el.appendChild(undoLink);
  }

  document.body.appendChild(el);
  setTimeout(() => el.remove(), showUndo ? 6000 : 3000);
}

/**
 * Undo optimization on the specified element.
 * @param {HTMLElement} targetEl - The element to restore
 */
function performUndo(targetEl) {
  if (!targetEl) return;
  const original = undoMap.get(targetEl);
  if (!original) return;
  writeText(targetEl, original);
  undoMap.delete(targetEl);
  targetEl.focus();
  showNotification("Restored original text");
}

/**
 * Core optimization logic shared by button click and hotkey.
 * @param {HTMLElement} targetEl - The element to optimize
 * @param {HTMLButtonElement} [btn] - The button element to update state on
 */
async function optimizeElement(targetEl, btn) {
  if (isCompressing) return;

  const text = readText(targetEl);
  if (!text.trim()) {
    showNotification("Nothing to optimize");
    return;
  }

  isCompressing = true;
  if (btn) {
    btn.textContent = "...";
    btn.disabled = true;
  }

  try {
    // Strip query params from URL before sending (privacy: no session tokens)
    const cleanUrl = location.origin;

    const response = await chrome.runtime.sendMessage({
      action: "compress",
      text,
      url: cleanUrl,
    });

    if (response.error) {
      showNotification(humanError(response.error));
      return;
    }

    if (response.compressed) {
      // Store original text for undo
      undoMap.set(targetEl, text);

      const wrote = writeText(targetEl, response.compressed);
      if (!wrote) {
        await copyToClipboard(response.compressed);
      } else if (response.savings_pct > 0) {
        showNotification(null, response.savings_pct, true, targetEl);
      } else {
        showNotification("Nothing to optimize (already efficient)");
      }

      // Update button with savings badge
      if (btn) {
        if (response.savings_pct > 0) {
          btn.textContent = `${response.savings_pct.toFixed(0)}%`;
          btn.classList.add("alientalk-btn--saved");
        } else {
          btn.textContent = "Optimize";
        }
      }

      // Return focus to the text field
      targetEl.focus();
    }
  } catch (err) {
    showNotification("Compression failed");
    console.error("[AlienTalk]", err);
  } finally {
    isCompressing = false;
    if (btn) {
      btn.disabled = false;
      if (btn.textContent === "...") {
        btn.textContent = "Optimize";
      }
    }
  }
}

/** Create and inject the optimize button into document.body. */
function injectButton() {
  // Remove stale button from previous SPA navigation
  const existing = document.querySelector(".alientalk-btn");
  if (existing) existing.remove();

  const site = getSiteName();
  const pos = getButtonPosition(site);

  const btn = document.createElement("button");
  btn.className = "alientalk-btn";
  btn.textContent = "Optimize";
  btn.title = "AlienTalk — Compress this prompt (Cmd+Shift+Enter)";
  btn.setAttribute("aria-label", "AlienTalk: Optimize prompt");
  btn.style.bottom = pos.bottom;
  btn.style.right = pos.right;

  btn.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();

    const targetEl = lastEditableEl;
    if (!targetEl) {
      showNotification("No focused text field");
      return;
    }

    await optimizeElement(targetEl, btn);
  });

  document.body.appendChild(btn);
}

/** Find the main chat input element. */
function findChatInput() {
  const selectors = [
    '[contenteditable="true"][role="textbox"]',
    '[contenteditable="true"][data-placeholder]',
    'textarea[placeholder]',
    'textarea',
  ];

  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el) return el;
  }
  return null;
}

/**
 * Watch for chat input to appear and re-inject button on SPA navigation.
 * Persistent observer handles route changes without page reloads.
 */
function watchForInput() {
  let hasInput = false;

  const observer = new MutationObserver(() => {
    const input = findChatInput();
    if (input && !hasInput) {
      hasInput = true;
      // Re-inject button if it was removed (SPA navigation)
      if (!document.querySelector(".alientalk-btn")) {
        injectButton();
      }
    } else if (!input && hasInput) {
      // Input removed (navigated away) — reset so we re-inject on next appearance
      hasInput = false;
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
}

// Listen for hotkey trigger from background script
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === "hotkey_optimize") {
    const targetEl = lastEditableEl;
    if (!targetEl) {
      showNotification("No focused text field");
      return;
    }
    const btn = document.querySelector(".alientalk-btn");
    optimizeElement(targetEl, btn);
  }
});

// Initialize
const site = getSiteName();
if (site) {
  injectButton();
  watchForInput();
}
