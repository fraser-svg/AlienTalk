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
 */
function showNotification(message, savingsPct) {
  const existing = document.querySelector(".alientalk-notification");
  if (existing) existing.remove();

  const el = document.createElement("div");
  el.className = "alientalk-notification";
  el.textContent = savingsPct != null
    ? `${savingsPct.toFixed(0)}% faster response`
    : message;
  document.body.appendChild(el);

  setTimeout(() => el.remove(), 3000);
}

/** Create and inject the optimize button into document.body. */
function injectButton() {
  // Remove stale button from previous SPA navigation
  const existing = document.querySelector(".alientalk-btn");
  if (existing) existing.remove();

  const btn = document.createElement("button");
  btn.className = "alientalk-btn";
  btn.textContent = "Optimize";
  btn.title = "AlienTalk — Compress this prompt";

  btn.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();

    // Use last-focused editable element, not document.activeElement
    // (clicking the button steals focus from the text field).
    const targetEl = lastEditableEl;
    if (!targetEl) {
      showNotification("No focused text field");
      return;
    }

    const text = readText(targetEl);
    if (!text.trim()) {
      showNotification("Nothing to optimize");
      return;
    }

    // Show loading state
    btn.textContent = "...";
    btn.disabled = true;

    try {
      // Strip query params from URL before sending (privacy: no session tokens)
      const cleanUrl = location.origin + location.pathname;

      const response = await chrome.runtime.sendMessage({
        action: "compress",
        text,
        url: cleanUrl,
      });

      if (response.error) {
        showNotification(`Error: ${response.error}`);
        return;
      }

      if (response.compressed) {
        const wrote = writeText(targetEl, response.compressed);
        if (!wrote) {
          await copyToClipboard(response.compressed);
        } else if (response.savings_pct > 0) {
          showNotification(null, response.savings_pct);
        }

        // Update button with savings badge
        if (response.savings_pct > 0) {
          btn.textContent = `${response.savings_pct.toFixed(0)}%`;
          btn.classList.add("alientalk-btn--saved");
        } else {
          btn.textContent = "Optimize";
        }
      }
    } catch (err) {
      showNotification("Compression failed");
      console.error("[AlienTalk]", err);
    } finally {
      btn.disabled = false;
      // Reset button text on error (don't leave it stuck on "...")
      if (btn.textContent === "...") {
        btn.textContent = "Optimize";
      }
    }
  });

  // Button is position:fixed, so append to body (not inside input wrappers
  // where it breaks flexbox layouts on target sites).
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

// Initialize
const site = getSiteName();
if (site) {
  injectButton();
  watchForInput();
}
