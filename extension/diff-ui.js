/**
 * AlienTalk — Diff UI overlay.
 *
 * Renders a before/after diff panel using shadow DOM for style isolation.
 * Shows removed text (red strikethrough) and added text (green highlight).
 */

/** @type {HTMLElement|null} Active diff container (shadow host). */
let activeDiffHost = null;

/**
 * Inline styles for the diff overlay (avoids web_accessible_resources).
 * Kept here so shadow DOM is fully self-contained.
 */
const DIFF_CSS = `
.alientalk-diff-overlay{position:fixed;bottom:140px;right:20px;z-index:10002;width:480px;max-width:calc(100vw - 40px);max-height:60vh;display:flex;flex-direction:column;background:#1a1a2e;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.5);font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;color:#e0e0e0;animation:at-diff-slide-in .2s ease}
@keyframes at-diff-slide-in{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.alientalk-diff-header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.08)}
.alientalk-diff-title{font-weight:600;font-size:13px;color:#e0e0e0}
.alientalk-diff-savings{font-size:12px;color:#4ecca3;font-weight:500}
.alientalk-diff-body{padding:14px 16px;overflow-y:auto;line-height:1.6;white-space:pre-wrap;word-break:break-word;flex:1;min-height:60px;max-height:40vh}
.alientalk-diff-removed{background:rgba(255,80,80,.15);color:#ff8888;text-decoration:line-through;border-radius:3px;padding:1px 2px}
.alientalk-diff-added{background:rgba(78,204,163,.15);color:#4ecca3;border-radius:3px;padding:1px 2px}
.alientalk-diff-footer{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:10px 16px;border-top:1px solid rgba(255,255,255,.08)}
.alientalk-diff-btn{border:none;border-radius:8px;padding:6px 16px;font-size:12px;font-weight:600;font-family:-apple-system,BlinkMacSystemFont,sans-serif;cursor:pointer;transition:background .15s ease,transform .1s ease}
.alientalk-diff-btn:active{transform:scale(.97)}
.alientalk-diff-btn--cancel{background:rgba(255,255,255,.08);color:#ccc}
.alientalk-diff-btn--cancel:hover{background:rgba(255,255,255,.14)}
.alientalk-diff-btn--apply{background:#4ecca3;color:#1a1a2e}
.alientalk-diff-btn--apply:hover{background:#5fd9b0}
.alientalk-diff-hint{font-size:11px;color:#666;margin-right:auto}
`;

/**
 * Show the diff overlay panel.
 *
 * @param {Array<{type: 'equal'|'removed'|'added', text: string}>} diffOps
 * @param {number} savingsPct
 * @param {function} onApply - Called when user clicks Apply.
 * @param {function} onCancel - Called when user clicks Cancel.
 */
function showDiffView(diffOps, savingsPct, onApply, onCancel) {
  // Remove any existing diff panel
  closeDiffView();

  const css = DIFF_CSS;

  // Create shadow host
  const host = document.createElement("div");
  host.id = "alientalk-diff-host";
  host.style.cssText = "all: initial; position: fixed; z-index: 10002; bottom: 0; right: 0;";

  const shadow = host.attachShadow({ mode: "closed" });

  // Inject styles
  const style = document.createElement("style");
  style.textContent = css;
  shadow.appendChild(style);

  // Build overlay
  const overlay = document.createElement("div");
  overlay.className = "alientalk-diff-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-label", "Compression diff preview");

  // Header
  const header = document.createElement("div");
  header.className = "alientalk-diff-header";

  const title = document.createElement("span");
  title.className = "alientalk-diff-title";
  title.textContent = "Compression Preview";

  const savings = document.createElement("span");
  savings.className = "alientalk-diff-savings";
  savings.textContent = savingsPct > 0 ? `${savingsPct.toFixed(0)}% smaller` : "";

  header.appendChild(title);
  header.appendChild(savings);
  overlay.appendChild(header);

  // Diff body
  const body = document.createElement("div");
  body.className = "alientalk-diff-body";

  for (const op of diffOps) {
    const span = document.createElement("span");
    if (op.type === "removed") {
      span.className = "alientalk-diff-removed";
    } else if (op.type === "added") {
      span.className = "alientalk-diff-added";
    }
    span.textContent = op.text;
    body.appendChild(span);
  }

  overlay.appendChild(body);

  // Footer
  const footer = document.createElement("div");
  footer.className = "alientalk-diff-footer";

  const hint = document.createElement("span");
  hint.className = "alientalk-diff-hint";
  hint.textContent = "Enter to apply · Esc to cancel";

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "alientalk-diff-btn alientalk-diff-btn--cancel";
  cancelBtn.textContent = "Cancel";
  cancelBtn.setAttribute("aria-label", "Cancel compression");

  const applyBtn = document.createElement("button");
  applyBtn.className = "alientalk-diff-btn alientalk-diff-btn--apply";
  applyBtn.textContent = "Apply";
  applyBtn.setAttribute("aria-label", "Apply compression");

  footer.appendChild(hint);
  footer.appendChild(cancelBtn);
  footer.appendChild(applyBtn);
  overlay.appendChild(footer);

  shadow.appendChild(overlay);
  document.body.appendChild(host);
  activeDiffHost = host;

  // Focus the apply button for keyboard accessibility
  applyBtn.focus();

  // Wire up buttons
  function handleApply() {
    closeDiffView();
    onApply();
  }

  function handleCancel() {
    closeDiffView();
    onCancel();
  }

  applyBtn.addEventListener("click", handleApply);
  cancelBtn.addEventListener("click", handleCancel);

  // Keyboard shortcuts (Enter = apply, Escape = cancel)
  // Only handle keys when focus is inside the diff panel
  function handleKeydown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      handleApply();
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      handleCancel();
    }
  }

  // Listen on the shadow root only — avoids capturing host page keypresses
  shadow.addEventListener("keydown", handleKeydown);

  // No document-level listener to clean up (shadow-only)
}

/**
 * Close and remove the diff overlay.
 */
function closeDiffView() {
  if (activeDiffHost) {
    if (activeDiffHost._cleanup) activeDiffHost._cleanup();
    activeDiffHost.remove();
    activeDiffHost = null;
  }
}
