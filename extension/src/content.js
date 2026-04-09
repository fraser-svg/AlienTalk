// Sharp content script — Stage 1 UI for supported AI chat sites.
// Self-contained (no ES module imports — MV3 content scripts don't support them).

(function () {
  "use strict";

  // ─── Site Adapters ─────────────────────────────────────────────

  const ADAPTERS = {
    claude: {
      name: "claude",
      pattern: /claude\.ai/,
      getInput() {
        return (
          document.querySelector('[contenteditable="true"].ProseMirror') ||
          document.querySelector('[contenteditable="true"][data-placeholder]') ||
          document.querySelector("fieldset .ProseMirror")
        );
      },
      readText(el) {
        if (!el) return "";
        const ps = el.querySelectorAll("p");
        if (ps.length) return Array.from(ps).map((p) => p.textContent).join("\n");
        return el.textContent || "";
      },
      writeText(el, text) {
        writeContentEditable(el, text);
      },
      badgePos: { bottom: "12px", right: "70px" },
    },
    chatgpt: {
      name: "chatgpt",
      pattern: /chatgpt\.com/,
      getInput() {
        return (
          document.querySelector("#prompt-textarea") ||
          document.querySelector('[contenteditable="true"][data-id="root"]')
        );
      },
      readText(el) {
        if (!el) return "";
        if (el.getAttribute("contenteditable") !== null) {
          const ps = el.querySelectorAll("p");
          if (ps.length) return Array.from(ps).map((p) => p.textContent).join("\n");
        }
        return el.textContent || el.value || "";
      },
      writeText(el, text) {
        if (el.getAttribute("contenteditable") !== null) {
          writeContentEditable(el, text);
        } else {
          writeNativeInput(el, text);
        }
      },
      badgePos: { bottom: "12px", right: "80px" },
    },
    gemini: {
      name: "gemini",
      pattern: /gemini\.google\.com/,
      getInput() {
        return (
          document.querySelector(".ql-editor[contenteditable='true']") ||
          document.querySelector("rich-textarea .ql-editor") ||
          document.querySelector('[contenteditable="true"][role="textbox"]')
        );
      },
      readText(el) {
        if (!el) return "";
        const ps = el.querySelectorAll("p");
        if (ps.length) return Array.from(ps).map((p) => p.textContent).join("\n");
        return el.textContent || "";
      },
      writeText(el, text) {
        writeContentEditable(el, text);
      },
      badgePos: { bottom: "8px", right: "60px" },
    },
    perplexity: {
      name: "perplexity",
      pattern: /perplexity\.ai/,
      getInput() {
        return (
          document.querySelector("textarea[placeholder*='Ask']") ||
          document.querySelector("textarea[placeholder*='ask']")
        );
      },
      readText(el) { return el?.value || ""; },
      writeText(el, text) { writeNativeInput(el, text); },
      badgePos: { bottom: "8px", right: "50px" },
    },
    poe: {
      name: "poe",
      pattern: /poe\.com/,
      getInput() {
        return (
          document.querySelector('[class*="ChatMessageInputContainer"] textarea') ||
          document.querySelector('[class*="TextArea"] textarea')
        );
      },
      readText(el) { return el?.value || ""; },
      writeText(el, text) { writeNativeInput(el, text); },
      badgePos: { bottom: "8px", right: "50px" },
    },
    huggingface: {
      name: "huggingface",
      pattern: /huggingface\.co\/chat/,
      getInput() {
        return (
          document.querySelector("textarea[placeholder*='message']") ||
          document.querySelector("textarea[enterkeyhint='send']")
        );
      },
      readText(el) { return el?.value || ""; },
      writeText(el, text) { writeNativeInput(el, text); },
      badgePos: { bottom: "8px", right: "50px" },
    },
  };

  function writeContentEditable(el, text) {
    if (!el) return;
    el.focus();
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand("insertText", false, text);
  }

  function writeNativeInput(el, text) {
    if (!el) return;
    const setter =
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set ||
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    if (setter) {
      setter.call(el, text);
    } else {
      el.value = text;
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function getAdapter() {
    const url = window.location.href;
    for (const a of Object.values(ADAPTERS)) {
      if (a.pattern.test(url)) return a;
    }
    return null;
  }

  // ─── JS Shim Engine (until WASM loads) ─────────────────────────

  const FILLER_PATTERNS = [
    [/\bI was wondering if you could\b/gi, ""],
    [/\bI want you to\b/gi, ""],
    [/\bI need you to\b/gi, ""],
    [/\bI'd like you to\b/gi, ""],
    [/\bcould you please\b/gi, ""],
    [/\bcan you please\b/gi, ""],
    [/\bplease make sure to\b/gi, ""],
    [/\bplease make sure\b/gi, ""],
    [/\bI think you should\b/gi, ""],
    [/\bthank you so much!?\b/gi, ""],
    [/\bthanks in advance\.?\b/gi, ""],
    [/\bthank you\.?\b/gi, ""],
    [/\bI appreciate your help\.?\b/gi, ""],
    [/^(hey|hi|hello),?\s*/i, ""],
    [/\bin order to\b/gi, "to"],
    [/\bdue to the fact that\b/gi, "because"],
    [/\bfor the purpose of\b/gi, "to"],
    [/\bwith regard to\b/gi, "about"],
    [/\bin the event that\b/gi, "if"],
    [/\bat this point in time\b/gi, "now"],
    [/\bhas the ability to\b/gi, "can"],
    [/\bis able to\b/gi, "can"],
    [/\btake into consideration\b/gi, "consider"],
    [/\btake into account\b/gi, "consider"],
    [/\bmake a decision\b/gi, "decide"],
    [/\bmake changes to\b/gi, "change"],
    [/\bmake improvements to\b/gi, "improve"],
    [/\bbasically,?\s*/gi, ""],
    [/\bessentially,?\s*/gi, ""],
    [/\bactually,?\s*/gi, ""],
  ];

  function shimSharpen(text) {
    let result = text;
    for (const [pat, rep] of FILLER_PATTERNS) {
      result = result.replace(pat, rep);
    }
    result = result.replace(/\s{2,}/g, " ").trim();
    if (result.length > 0 && /^[a-z]/.test(result)) {
      result = result[0].toUpperCase() + result.slice(1);
    }
    return result;
  }

  function shimScore(text) {
    const words = text.split(/\s+/).filter(Boolean);
    let score = 50;
    const filler = ["just", "really", "basically", "actually", "literally", "very", "quite"];
    score -= words.filter((w) => filler.includes(w.toLowerCase())).length * 5;
    if (/\d/.test(text)) score += 10;
    if (text.includes("```")) score += 5;
    if (words.length > 5 && words.length < 50) score += 10;
    if (/^(explain|create|write|build|fix|debug|analyze|compare|list)/i.test(text)) score += 10;
    return Math.max(0, Math.min(100, score));
  }

  const engine = {
    sharpen: shimSharpen,
    score: shimScore,
  };

  // Try loading WASM engine as upgrade
  async function loadWasm() {
    try {
      const jsUrl = chrome.runtime.getURL("wasm/pkg/sharp_engine.js");
      const wasmUrl = chrome.runtime.getURL("wasm/pkg/sharp_engine_bg.wasm");
      // Fetch and eval the JS bindings (content script can't use import())
      const jsCode = await (await fetch(jsUrl)).text();
      // The wasm-bindgen JS expects to fetch the wasm file by URL.
      // We need to patch the init function to use our chrome-extension URL.
      const blob = new Blob(
        [jsCode.replace(/sharp_engine_bg\.wasm/g, wasmUrl)],
        { type: "text/javascript" }
      );
      const blobUrl = URL.createObjectURL(blob);
      try {
        const mod = await import(blobUrl);
        await mod.default();
        engine.sharpen = mod.wasm_sharpen;
        engine.score = mod.wasm_score;
        console.log("[Sharp] WASM engine loaded");
      } finally {
        URL.revokeObjectURL(blobUrl);
      }
    } catch (e) {
      console.log("[Sharp] WASM unavailable, using JS shim:", e.message);
    }
  }

  // ─── Badge UI ──────────────────────────────────────────────────

  const BADGE_ID = "sharp-badge";
  const UNDO_ID = "sharp-undo";
  let undoTimeout = null;
  let undoData = null;

  function createBadge() {
    if (document.getElementById(BADGE_ID)) return;
    const b = document.createElement("div");
    b.id = BADGE_ID;
    b.className = "sharp-badge";
    b.setAttribute("role", "button");
    b.setAttribute("tabindex", "0");
    b.setAttribute("aria-label", "Sharp prompt quality score");
    b.title = "Click to sharpen (Cmd+Shift+S)";
    b.textContent = "--";
    document.body.appendChild(b);
    b.addEventListener("click", sharpenPrompt);
    b.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sharpenPrompt(); }
    });
  }

  function updateBadge(score, pos) {
    const b = document.getElementById(BADGE_ID);
    if (!b) return;
    b.textContent = String(score);
    b.classList.remove("sharp-badge--low", "sharp-badge--mid", "sharp-badge--high");
    if (score < 40) b.classList.add("sharp-badge--low");
    else if (score < 70) b.classList.add("sharp-badge--mid");
    else b.classList.add("sharp-badge--high");
    if (pos) { b.style.bottom = pos.bottom; b.style.right = pos.right; }
    b.classList.add("sharp-badge--visible");
  }

  function showTransition(before, after) {
    const b = document.getElementById(BADGE_ID);
    if (!b) return;
    b.textContent = `${before} → ${after}`;
    b.classList.add("sharp-badge--transition");
    setTimeout(() => {
      b.textContent = String(after);
      b.classList.remove("sharp-badge--transition");
      b.classList.remove("sharp-badge--low", "sharp-badge--mid", "sharp-badge--high");
      if (after >= 70) b.classList.add("sharp-badge--high");
      else if (after >= 40) b.classList.add("sharp-badge--mid");
      else b.classList.add("sharp-badge--low");
    }, 2000);
  }

  function hideBadge() {
    const b = document.getElementById(BADGE_ID);
    if (b) b.classList.remove("sharp-badge--visible");
  }

  function showUndo(el, originalText, adapter) {
    removeUndo();
    undoData = { el, originalText, adapter };
    const u = document.createElement("div");
    u.id = UNDO_ID;
    u.className = "sharp-undo";
    const span = document.createElement("span");
    span.className = "sharp-undo__text";
    span.textContent = "Sharpened";
    const btn = document.createElement("button");
    btn.className = "sharp-undo__btn";
    btn.textContent = "Undo";
    btn.addEventListener("click", () => {
      if (undoData) undoData.adapter.writeText(undoData.el, undoData.originalText);
      removeUndo();
    });
    u.appendChild(span);
    u.appendChild(btn);
    document.body.appendChild(u);
    undoTimeout = setTimeout(removeUndo, 5000);
  }

  function removeUndo() {
    if (undoTimeout) { clearTimeout(undoTimeout); undoTimeout = null; }
    const u = document.getElementById(UNDO_ID);
    if (u) u.remove();
    undoData = null;
  }

  // ─── Core Logic ────────────────────────────────────────────────

  let adapter = null;
  let isSharpening = false;
  let lastPolledText = "";

  function pollInput() {
    if (!adapter) return;
    const el = adapter.getInput();
    if (!el) { hideBadge(); return; }
    const text = adapter.readText(el).trim();
    if (!text || text.split(/\s+/).length < 3) { hideBadge(); lastPolledText = ""; return; }
    if (text === lastPolledText) return;
    lastPolledText = text;
    const score = engine.score(text);
    updateBadge(score, adapter.badgePos);
  }

  function sharpenPrompt() {
    if (!adapter || isSharpening) return;
    const el = adapter.getInput();
    if (!el) return;
    const original = adapter.readText(el).trim();
    if (!original || original.split(/\s+/).length < 5) return;

    isSharpening = true;
    try {
      const scoreBefore = engine.score(original);
      const sharpened = engine.sharpen(original);
      const scoreAfter = engine.score(sharpened);
      if (sharpened === original) return;

      adapter.writeText(el, sharpened);
      showTransition(scoreBefore, scoreAfter);
      showUndo(el, original, adapter);

      // Update stats
      const saved = original.split(/\s+/).length - sharpened.split(/\s+/).length;
      chrome.storage.local.get(["promptCount", "tokensSaved"], (data) => {
        chrome.storage.local.set({
          promptCount: (data.promptCount || 0) + 1,
          tokensSaved: (data.tokensSaved || 0) + Math.max(0, saved),
        });
      });
    } catch (e) {
      console.error("[Sharp] Sharpen failed:", e);
    } finally {
      isSharpening = false;
    }
  }

  // Listen for hotkey from background (validate sender is this extension)
  chrome.runtime.onMessage.addListener((msg, sender) => {
    if (sender.id !== chrome.runtime.id) return;
    if (msg.action === "sharpen") sharpenPrompt();
  });

  // ─── Init ──────────────────────────────────────────────────────

  adapter = getAdapter();
  if (!adapter) return;
  console.log(`[Sharp] Active on ${adapter.name}`);

  createBadge();
  loadWasm(); // Non-blocking: upgrades engine when ready
  setInterval(pollInput, 1000);

  // SPA navigation: re-check adapter on URL changes (not every DOM mutation)
  function recheckAdapter() {
    const next = getAdapter();
    if (next && next.name !== adapter.name) adapter = next;
  }
  window.addEventListener("popstate", recheckAdapter);
  window.addEventListener("hashchange", recheckAdapter);
  // Fallback for SPAs that use pushState without popstate events
  new MutationObserver(recheckAdapter).observe(document.body, { childList: true, subtree: false });
})();
