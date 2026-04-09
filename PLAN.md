<!-- /autoplan restore point: /Users/foxy/.gstack/projects/fraser-svg-AlienTalk/fraser-svg-autoplan-product-ux-autoplan-restore-20260409-115658.md -->
# Plan: AlienTalk v0.3 — Grammarly-Level Frictionlessness

**Branch:** fraser-svg/autoplan-product-ux
**Base:** v0.2.1.0 (daemon + extension + spell correction shipped)
**Input:** External product review identifying 6 gaps between current state and "just works" UX

## Problem Statement

AlienTalk has three surfaces (Python engine, macOS daemon, Chrome extension) but they don't form one product yet. A user must understand all three exist, install each separately, and keep the daemon running for the extension to work. Grammarly's genius: install one thing, everything else bootstraps.

## Current State

- Python engine: 180+ tests, spell correction, 4-step pipeline, Prime features
- Rust daemon: Tauri v2 menu bar app, 24 tests, PyO3 bridge (scaffolding), accessibility API
- Chrome extension: MV3, native messaging to daemon, Optimize button, hotkey, ProseMirror write-back
- 7 integration methods: SDK wrapper, API proxy, REPL, CLI pipe, MCP server, daemon, extension

## Priority Sequence

### Priority 1: Kill the Python dependency

**Problem:** Daemon bridges to Python engine via PyO3. User needs Python 3.9+ with dev headers. Most "power users who chat with Claude all day" don't have this.

**Option A: Bundle Python runtime** — PyOxidizer or python-build-standalone freezes engine into self-contained binary. ~30MB. No system Python. Grammarly path: zero prerequisites.

**Option B: Rewrite engine in Rust** — The 4-step pipeline (spell correction, pattern replacement, filler removal, structure cleanup) is deterministic string manipulation. No ML models. Well-suited to Rust. Eliminates Python bridge entirely. Longer effort but removes the biggest architectural friction.

**Decision: Option B chosen.** Rewrite engine in Rust. Single codebase compiles to native (daemon) and WASM (extension). Eliminates Python bridge, PyO3, python-build-standalone complexity. The 4-step pipeline is deterministic string manipulation, well-suited to Rust. SymSpell has a Rust crate. Phase B (WASM fallback) becomes a compile target, not a separate port.

**Existing code:**
- `engine/alchemist.py` — 4-step pipeline (~800 lines)
- `engine/spell.py` — SymSpell wrapper (~375 lines)
- `engine/alchemist_prime.py` — Prime features (~900 lines)
- `daemon/src/bridge.rs` — PyO3 bridge (scaffolding)

### Priority 2: Daemon onboarding flow

**Problem:** No guided setup. User must manually: install .dmg, grant Accessibility permission, discover Chrome extension exists, sideload it. Each step is a drop-off point.

**Proposed solution:** First-launch wizard in daemon:
1. Welcome screen explaining what AlienTalk does
2. Accessibility permission request with visual guide
3. Chrome extension install prompt (link to CWS listing, or open Web Store page)
4. Connection verification (daemon <-> extension handshake)
5. Test compression on sample prompt

**Existing code:**
- `daemon/src/tray.rs` — Menu bar UI (basic)
- `daemon/src/config.rs` — Settings management
- No onboarding flow exists

### Priority 3: WASM fallback in Chrome extension

**Problem:** Extension is dead without daemon running. For viral distribution, extension should work standalone.

**Proposed solution:** Compile core compression pipeline to WASM. Extension bundles it as fallback:
- Daemon running? Use native messaging (faster, Prime features)
- Daemon not running? Run WASM engine in-browser (core pipeline only)

**This means someone can install just the Chrome extension and get value immediately.** That's the viral distribution channel.

**Existing code:**
- `extension/background.js` — Already has daemon connection handling
- `extension/content.js` — Already has fallback messaging for when daemon disconnects
- Engine pipeline is deterministic string manipulation (WASM-compatible)

### Priority 4: Auto-compression on submit intercept

**Problem:** "Optimize" button requires conscious action. Grammarly doesn't have a "Check Grammar" button.

**Proposed solution:** Detect form submission on chat interfaces. Intercept, compress, then let submit proceed:
- Debounce on keystroke pause (show "42% smaller" indicator)
- OR intercept Enter/submit, compress, submit compressed version
- Small indicator showing savings with undo option
- User types naturally, compression is invisible

**Chrome Web Store concern:** CWS policy section 4.4 requires user-initiated actions for input modification. Auto-intercept may violate this. Need CWS policy review.

**Existing code:**
- `extension/content.js` — Button injection, site-specific positioning, ProseMirror write-back
- Current model is explicitly user-initiated (button click or hotkey)

### Priority 5: Trust-building diff view

**Problem:** "Is it going to break my prompts?" Users don't trust invisible modification.

**Proposed solution:** Onboarding period (first ~50 compressions):
- Show split view: "Your prompt" vs "Optimized prompt" with inline diff
- Let user see what changed before accepting
- After trust threshold, switch to silent mode (with option to always show)

**Existing code:**
- Extension already shows savings percentage in toast
- No diff view exists

### Priority 6: Reposition REPL for subscription users

**Problem:** REPL is buried under six other integration methods. But it's the killer feature for Claude MAX / Codex users who can't use the SDK wrapper (no API keys) but burn through subscription rate limits.

**Proposed solution:**
- Reposition REPL as headline feature for subscription users
- Value prop: "Send more messages before hitting your limit"
- Separate README section or landing page for subscription users
- Move REPL above SDK wrapper in integration hierarchy for non-API users

**Existing code:**
- `engine/integrations/repl.py` — Working REPL with claude/codex backends
- README currently lists REPL third after SDK wrapper and API proxy

## Audience Simplification

From 7 integration methods to 3 entry points:
1. **Chrome extension** — For chat users (claude.ai, chatgpt, gemini)
2. **macOS daemon** — For power users (system-wide, any app)
3. **SDK wrapper** — For developers (API integration)

Everything else (proxy, REPL, pipe, MCP) = advanced features in docs, not README.

## Phasing

**Phase A (ship first):** P1 (rewrite engine in Rust) + P2 (onboarding flow) + P5 (diff view)
**Phase B:** P3 (WASM fallback from Rust engine, no separate port needed)
**Phase C:** P4 (auto-compression, after CWS policy validation) + P6 (REPL repositioning)

> **Decision: Option B chosen.** Rewrite compression engine in Rust. Eliminates Python
> dependency entirely. Rust engine compiles to native (daemon) AND WASM (extension
> fallback) from single codebase. Phase B becomes trivial since WASM is a compile
> target of the same Rust engine.
>
> **Decision: Diff view moved to Phase A.** Trust mechanism ships with first compression.
> 4/4 review voices across 3 phases agreed.

## Open Questions

1. ~~Option A vs B for Python dependency?~~ **RESOLVED: Option B (Rust rewrite)**
2. CWS policy compatibility for auto-compression?
3. WASM bundle size for in-browser engine?
4. How to handle Prime features (code minifier, snippet cache) in WASM path?

---

# PHASE 1: CEO REVIEW

**Mode:** SELECTIVE EXPANSION (auto-decided, P3: feature iteration on existing product)

## Step 0A: Premise Challenge

The plan rests on 5 premises. Three are shaky.

| # | Premise | Valid? | Risk |
|---|---------|--------|------|
| 1 | "Installation friction is the main blocker to adoption" | ASSUMED | No user data. Could be trust, value perception, or awareness. |
| 2 | "Grammarly's architecture is the right model" | PARTIALLY | Grammarly edits low-stakes text. Prompt compression modifies high-stakes model instructions. Semantic drift is the cost of error. Different product category. |
| 3 | "The Chrome extension is the viral distribution channel" | REASONABLE | But only if it works standalone (P3). Currently requires daemon = not viral at all. |
| 4 | "Auto-compression is the endgame UX" | RISKY | CWS policy 4.4 may block this entirely. Plan acknowledges the risk but schedules it Phase C without a validation step. |
| 5 | "Deterministic string manipulation is enough" | TRUE FOR NOW | No ML needed for current pipeline. But Token Company (YC W26) using ML may achieve higher compression ratios. Monitor. |

**Critical gap:** No success metrics defined. No kill criteria. The plan has no way to tell you whether it's working. What's the activation metric? Week-1 retention? Undo rate (trust signal)? Semantic regression rate?

## Step 0B: Existing Code Leverage

| Sub-problem | Existing Code | Reuse? |
|-------------|---------------|--------|
| Compression pipeline | `engine/alchemist.py` (800 LOC, 180+ tests) | YES, core asset |
| Spell correction | `engine/spell.py` (375 LOC, 71 tests) | YES |
| Native messaging bridge | `extension/background.js` (174 LOC) | YES, works |
| Daemon framework | `daemon/src/` (24 tests) | YES, but bridge.rs is scaffolding |
| REPL | `engine/integrations/repl.py` | YES, works today |
| API proxy | `engine/integrations/proxy.py` | YES, 80% of a hosted service |

The existing proxy.py is an overlooked asset. Hosting it as a service would give API users zero-install compression immediately.

## Step 0C: Dream State Mapping

```
CURRENT STATE                    THIS PLAN                      12-MONTH IDEAL
3 disconnected surfaces  --->    3 connected surfaces    --->   Invisible compression layer
Extension needs daemon           Extension works alone           across all AI interfaces.
No onboarding                    Guided first-run               User doesn't think about it.
Manual button click              Auto-compression               "My prompts are just better."
7 integration methods            3 entry points                 1 entry point per audience.
0 users                          Early adopters                 Organic growth via extension.
```

**Gap after this plan ships:** Still no monetization path. Still no competitive moat beyond "we shipped first." Still no enterprise story (team policies, analytics, governance).

## Step 0C-bis: Implementation Alternatives

```
APPROACH A: Browser-First (RECOMMENDED)
  Summary: Ship WASM Chrome extension first. Works standalone. No daemon needed.
  Effort:  M (2-3 weeks)
  Risk:    Low (WASM compilation of Python-like string ops is well-trodden)
  Pros:    - Fastest path to user validation
           - Zero-install for Chrome users
           - Viral distribution channel activates immediately
  Cons:    - No Prime features in browser
           - Daemon work delayed
  Reuses:  engine/alchemist.py logic (rewritten to Rust/WASM)

APPROACH B: Daemon-First (current plan)
  Summary: Bundle Python in daemon, add onboarding, ship .dmg.
  Effort:  L (4-6 weeks)
  Risk:    Medium (PyOxidizer bundling, notarization, onboarding UI)
  Pros:    - System-wide compression
           - Full feature set including Prime
  Cons:    - macOS only
           - High install friction (Accessibility permissions)
           - No viral distribution
  Reuses:  daemon/src/ scaffolding, engine/ Python directly

APPROACH C: Hosted Proxy-First
  Summary: Host proxy.py as api.alientalk.com. API users change one URL.
  Effort:  S (1 week)
  Risk:    Low (proxy already works)
  Pros:    - Zero client install for API users
           - Revenue potential (metered usage)
           - Already 80% built
  Cons:    - Only serves API users, not chat users
           - Hosting costs
  Reuses:  engine/integrations/proxy.py
```

**Auto-decision (P1 completeness, P6 bias to action):** Recommend APPROACH A (Browser-First). It validates demand fastest with the lowest effort. Approach C is a parallel low-effort win.

## Step 0D: Selective Expansion Analysis

**Hold scope analysis:**
- Complexity check: Plan touches 6 systems (Python engine, Rust daemon, Chrome extension, WASM compiler, onboarding UI, REPL positioning). That's >8 conceptual components. Challenge: can we achieve the core goal with fewer?
- Minimum viable: Ship standalone Chrome extension (P3) + trust diff (P5) + REPL repositioning (P6). Three changes, two surfaces touched, highest validation value.

**Expansion candidates (auto-decided per 6 principles):**

| # | Expansion | Effort | Decision | Principle |
|---|-----------|--------|----------|-----------|
| E1 | Success metrics + kill criteria per phase | S | ACCEPTED | P1 (completeness) |
| E2 | Hosted proxy as parallel zero-install path | S | ACCEPTED | P6 (action) + P4 (DRY, proxy exists) |
| E3 | VS Code/Cursor extension via MCP server | M | DEFERRED | P3 (pragmatic, MCP server exists but scope too wide for this plan) |
| E4 | Enterprise prompt governance layer | L | DEFERRED | P3 (ocean, not lake) |
| E5 | Competitive benchmark dashboard (vs Token Company) | S | ACCEPTED | P1 (completeness, need to track competitive position) |

## Step 0E: Temporal Interrogation

```
HOUR 1 (foundations):    Which compression engine target? Rust WASM or port Python?
                         Answer: Rust. The 4-step pipeline is string ops. ~1200 LOC to port.
                         SymSpell has a Rust crate (symspell). Patterns are regex.
HOUR 2-3 (core logic):  WASM bundle size. Will the SymSpell dictionary fit?
                         30MB dictionary is too large for WASM. Need smaller dict or lazy load.
HOUR 4-5 (integration): How does WASM fallback integrate with existing native messaging?
                         background.js already handles disconnection. Add WASM path there.
HOUR 6+ (polish/tests): How to test parity between Rust/WASM engine and Python engine?
                         Run both engines on same test corpus, diff outputs.
```

## Step 0F: Mode Confirmation

**Mode: SELECTIVE EXPANSION** with Browser-First approach.
**Accepted expansions:** E1 (metrics), E2 (hosted proxy), E5 (competitive benchmark).
**Deferred:** E3 (VS Code), E4 (enterprise).

---

## CLAUDE SUBAGENT (CEO, strategic independence)

8 findings, 4 CRITICAL:

1. **CRITICAL:** Priorities inverted. Chrome standalone (P3) is the only viral channel but it's Phase B. Ship it first.
2. **CRITICAL:** Core value prop may be imperceptible. 10-20% savings on short prompts = no perceived speed difference.
3. **CRITICAL:** 6-month regret: Rust rewrite takes 8 weeks, Token Company ships browser extension with ML compression during that time.
4. **CRITICAL:** Zero competitive analysis, no kill criteria.
5. **HIGH:** Five unstated premises with no validation gates.
6. **HIGH:** Three alternatives not analyzed (browser-only, VS Code, hosted proxy).
7. **MEDIUM:** bridge.rs is 100% scaffolding, daemon currently does nothing.
8. **MEDIUM:** Auto-compression (P4) sequenced after trust-building diff (P5) but diff must come first.

## CODEX SAYS (CEO, strategy challenge)

5 blind spots:

1. Optimizing install friction before proving the core value loop. No evidence users churn because of setup.
2. Grammarly analogy is weak. Grammarly edits low-stakes text; prompt compression modifies high-stakes model instructions.
3. "Extension-only = viral" is asserted, not defended. No distribution model, retention mechanism, or conversion path.
4. Auto-compression likely violates CWS policy 4.4. Phase C collapses if blocked.
5. Architecture drifting toward permanent complexity: Python + daemon + WASM (+ maybe Rust rewrite) = multiple engines, behavior drift, test matrix explosion.

Alternative suggestions: single-surface wedge, enterprise/API wedge, reliability-first wedge.

Missing from plan: success metrics, kill criteria, pricing/monetization tied to customer pain.

## CEO DUAL VOICES, CONSENSUS TABLE

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   NO      NO     CONFIRMED: premises unvalidated
  2. Right problem to solve?           MAYBE   NO     DISAGREE: Claude says reorder,
                                                      Codex says validate value first
  3. Scope calibration correct?        NO      NO     CONFIRMED: priorities inverted
  4. Alternatives sufficiently         NO      NO     CONFIRMED: 3+ missing
     explored?
  5. Competitive/market risks          NO      NO     CONFIRMED: zero analysis
     covered?
  6. 6-month trajectory sound?         NO      NO     CONFIRMED: Rust rewrite risk
═══════════════════════════════════════════════════════════════
CONFIRMED = both agree. DISAGREE = models differ (taste decision).
5/6 CONFIRMED. 1 DISAGREE (surfaced at gate).
```

---

## Review Sections 1-11

### Section 1: Architecture Review

```
                     ┌──────────────────┐
                     │ Chrome Extension  │
                     │ (content.js)      │
                     └────────┬─────────┘
                              │ chrome.runtime.sendMessage
                     ┌────────▼─────────┐
                     │ Background SW     │
                     │ (background.js)   │
                     └────────┬─────────┘
                              │ Native Messaging (JSON/stdio)
                     ┌────────▼─────────┐
                     │ Rust Daemon       │
                     │ (pipeline.rs)     │
                     │ queue → bridge    │
                     └────────┬─────────┘
                              │ PyO3 (spawn_blocking)
                     ┌────────▼─────────┐
                     │ Python Engine     │
                     │ (alchemist.py)    │
                     └──────────────────┘
```

**After this plan (Browser-First approach):**

```
                     ┌──────────────────┐
                     │ Chrome Extension  │
                     │ (content.js)      │
                     └────────┬─────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
           ┌───────▼────────┐  ┌────────▼────────┐
           │ WASM Engine    │  │ Native Messaging │
           │ (fallback)     │  │ (when daemon up) │
           │ Core pipeline  │  │ Full pipeline    │
           └────────────────┘  └─────────┬────────┘
                                         │
                               ┌─────────▼────────┐
                               │ Rust Daemon       │
                               │ + Python Engine   │
                               └──────────────────┘
```

**Coupling concern:** Two compression engines (WASM + Python) must produce identical output. This is the "behavior drift" risk Codex flagged. Mitigation: shared test corpus, CI that runs both engines and diffs outputs.

**Single point of failure:** Python bridge. Currently scaffolding. If it fails, the whole daemon path is dead. Fail-safe: already returns original text on any error. Good.

**Scaling:** Not applicable yet (single-user local tool). 10x load = user typing very fast. Queue handles this.

### Section 2: Error and Rescue Map

```
METHOD/CODEPATH              | WHAT CAN GO WRONG            | EXCEPTION
-----------------------------|------------------------------|-----------
WASM engine init             | WASM fails to load           | RuntimeError
                             | Dictionary too large for mem  | OOM
WASM compress()              | Regex engine divergence      | Silent wrong output ← CRITICAL
                             | Unicode edge case            | Encoding error
Extension→Daemon native msg  | Daemon not running           | disconnect event
                             | Daemon crashes mid-request   | timeout (3s)
                             | Malformed JSON response      | parse error
Daemon→Python bridge         | Python not found             | degraded mode
                             | Python crashes               | passthrough
                             | Timeout (>200ms)             | passthrough
Auto-compress submit intercept| CWS blocks the extension    | Extension removed ← CRITICAL
                             | Submit timing race           | Double submit
                             | ProseMirror update conflict  | Garbled text

EXCEPTION CLASS              | RESCUED? | RESCUE ACTION           | USER SEES
-----------------------------|----------|-------------------------|------------------
WASM RuntimeError            | N ← GAP  | —                       | Extension broken
WASM OOM                     | N ← GAP  | —                       | Extension broken
Regex divergence             | N ← GAP  | —                       | Silently wrong ← BAD
disconnect event             | Y        | Fallback to WASM        | "Using local engine"
timeout (native msg)         | Y        | resolve with error      | "Timed out"
Python degraded mode         | Y        | passthrough             | Original text shown
CWS removal                  | N ← GAP  | —                       | Extension gone ← BAD
```

**CRITICAL GAPS:**
1. WASM engine errors have no rescue. Need: try/catch around WASM init with fallback to "compression unavailable" state.
2. Regex divergence between Python and WASM/Rust is silent. Need: parity test suite running in CI.
3. CWS removal risk for auto-compression. Need: validate policy before building P4.

### Section 3: Security and Threat Model

| Threat | Likelihood | Impact | Mitigated? |
|--------|-----------|--------|------------|
| Prompt injection via compression output | Low | High | NO. Compression could theoretically create injection patterns from safe input. Need: output validation. |
| Extension reads all text in AI chat fields | High (by design) | Medium | PARTIAL. Content script has access to all page text. Need: clear privacy policy. |
| Native messaging host hijacking | Low | High | YES. Chrome verifies native host manifest. |
| WASM bundle tampering (CWS update) | Low | Medium | YES. CWS code signing. |
| Clipboard data exposure (fallback path) | Medium | Medium | PARTIAL. Clipboard copy on write failure. Need: clear clipboard after paste. |

No new external dependencies. No secrets. No PII collection. Security posture is reasonable for a local tool.

### Section 4: Data Flow and Edge Cases

```
USER TEXT ──▶ READ ELEMENT ──▶ COMPRESS ──▶ WRITE BACK ──▶ SHOW SAVINGS
    │              │              │              │              │
    ▼              ▼              ▼              ▼              ▼
  [empty?]    [no editable?]  [WASM fail?]  [write fail?]  [0% savings?]
  [huge?]     [shadow DOM?]   [timeout?]    [app blocks?]  [negative?]
  [code only?][iframe?]       [>original?]  [cursor lost?]
```

| Interaction | Edge Case | Handled? |
|-------------|-----------|----------|
| Optimize button | Double-click | YES (isCompressing flag) |
| Optimize button | Empty field | NO ← GAP (should skip) |
| Auto-compress | User still typing | Design gap: debounce needed |
| Auto-compress | Rapid Enter keypresses | NO ← GAP (race condition) |
| WASM fallback | First load (cold) | NO ← GAP (need loading state) |
| Diff view | Very long prompt | NO ← GAP (need truncation/scroll) |
| Undo | Multiple compressions | PARTIAL (WeakMap stores one undo per element) |

### Section 5: Code Quality Review

- `extension/background.js` duplicates request pattern between `sendCompressionRequest` and `requestStats`. Could be a shared `sendNativeRequest(action, payload)`. (P4: DRY)
- `daemon/src/bridge.rs` has 3 TODO comments. Entire `call_python_engine` is placeholder. Plan must address this.
- No linting or formatting config for extension JS. Should add eslint.
- Pipeline test (`pipeline.rs:116-135`) notes shared global state issue. Should use `serial_test::serial`.

### Section 6: Test Review

```
NEW UX FLOWS:
  - WASM fallback compression (standalone extension)
  - Diff view (before/after comparison)
  - Auto-compression on submit
  - Onboarding wizard (daemon)
  - Trust threshold transition (diff → silent)

NEW DATA FLOWS:
  - Text → WASM engine → compressed text (browser-only path)
  - Text → diff renderer → side-by-side view
  - Keystroke debounce → compression → submit intercept

NEW CODEPATHS:
  - WASM init + fallback logic in background.js
  - Parity checking between WASM and Python engines
  - Diff computation and rendering
  - Trust counter (compression count → mode switch)

NEW ERROR/RESCUE PATHS:
  - WASM load failure → "compression unavailable"
  - WASM OOM → passthrough
  - Submit intercept timing race → duplicate submission guard
```

**Missing tests:**
- WASM/Python parity test suite (run same inputs through both, diff)
- WASM cold-start performance test (<50ms target)
- Extension behavior when WASM and daemon both unavailable
- Diff view with edge cases (empty, huge, code-only prompts)
- Trust threshold state persistence across extension restarts

**Test ambition check:**
- 2am Friday test: WASM engine produces identical output to Python for top 100 prompt patterns
- Hostile QA test: prompt that compresses to something the LLM interprets differently
- Chaos test: daemon crashes during compression while WASM is loading

### Section 7: Performance Review

- WASM cold start: target <50ms. SymSpell dictionary load is the bottleneck. 30MB dict is too large for WASM memory. Need: smaller dictionary or lazy loading.
- WASM compression: target <20ms per prompt (match daemon SLA).
- Diff rendering: O(n) on prompt length. For 10K char prompts, need virtual scrolling.
- No N+1 queries (local tool). No DB. No connection pools.

### Section 8: Observability and Debuggability

- Extension: `console.log/warn` only. Need: structured logging with compression stats.
- Daemon: has `tracing` crate. Good.
- Missing: compression parity monitoring (alert when WASM and daemon produce different output for same input).
- Missing: undo rate tracking (signal of trust/distrust).
- Missing: WASM fallback activation rate (how often is daemon unavailable?).

### Section 9: Deployment and Rollout

- Chrome extension: CWS review 1-3 days. WASM bundle increases review scrutiny. Submit early.
- Daemon: .dmg + notarization. No change from current plan.
- Rollout order: Extension first (zero-install), daemon second (power users).
- Rollback: CWS unpublish + revert to daemon-only extension.
- Feature flags: WASM fallback should be toggleable in extension settings.

### Section 10: Long-Term Trajectory

- **Technical debt:** Two compression engines (Python + Rust/WASM). This is intentional, not debt, IF parity tests exist.
- **Path dependency:** Rust engine becomes the canonical implementation. Python engine becomes the test reference. This is fine.
- **Reversibility:** 4/5. Extension can always fall back to daemon-only. WASM is additive.
- **The 1-year question:** This plan moves toward the right architecture. A new engineer would understand "browser has fallback WASM engine, daemon has full engine."
- **What comes next:** Enterprise features, team policies, analytics dashboard.

### Section 11: Design and UX Review

**Information hierarchy:**
1. User sees: their text field (unchanged)
2. After compression: savings indicator (small, non-intrusive)
3. On hover/click: diff view (optional during onboarding)
4. In popup: stats dashboard

**Interaction state coverage:**

| Feature | Loading | Empty | Error | Success | Partial |
|---------|---------|-------|-------|---------|---------|
| Optimize button | Spinner | Skip | Toast | Toast + % | N/A |
| Auto-compress | Indicator | Skip | Silent pass | Indicator | N/A |
| Diff view | — | "Nothing to compare" | — | Side-by-side | Truncated |
| WASM fallback | "Loading engine..." | — | "Unavailable" | Transparent | — |
| Onboarding | Step progress | — | Retry step | Checkmark | Back button |

**Missing states:** WASM loading state, diff view empty state, onboarding error recovery.

---

## NOT in scope

| Item | Rationale |
|------|-----------|
| Windows/Linux daemon | macOS first, validate demand |
| Firefox extension | Chrome first, CWS is 65% market |
| LLM rewrite layer (Ollama) | Phase 2 per original CEO plan |
| Plugin system | Phase 3 per original CEO plan |
| VS Code/Cursor extension | Deferred (E3), MCP server exists as stopgap |
| Enterprise governance | Deferred (E4), ocean not lake |

## What already exists

| Sub-problem | Existing code | Plan reuses? |
|-------------|---------------|--------------|
| 4-step compression | engine/alchemist.py | YES, port to Rust/WASM |
| Spell correction | engine/spell.py + symspell | YES, Rust symspell crate |
| Native messaging | extension/background.js | YES, add WASM fallback branch |
| Disconnect handling | background.js reconnect logic | YES, trigger WASM instead |
| API proxy | engine/integrations/proxy.py | YES, host as service (E2) |
| REPL | engine/integrations/repl.py | YES, reposition in docs |
| Stats tracking | daemon/src/stats.rs | YES, extend for extension-local stats |

## Dream state delta

After this plan: standalone Chrome extension works, daemon is polished for power users, REPL is visible to subscription users. Gap to 12-month ideal: no monetization, no enterprise story, no ML compression, no cross-platform.

## Error and Rescue Registry

(See Section 2 above for complete table)

**CRITICAL GAPS: 3**
1. WASM engine errors unrescued
2. Regex divergence between engines is silent
3. CWS policy risk for auto-compression unvalidated

## Failure Modes Registry

```
CODEPATH           | FAILURE MODE        | RESCUED? | TEST? | USER SEES?  | LOGGED?
-------------------|---------------------|----------|-------|-------------|--------
WASM init          | Load failure        | N        | N     | Silent ← BAD| N
WASM compress      | Regex divergence    | N        | N     | Silent ← BAD| N
Auto-compress      | Race condition      | N        | N     | Double sub  | N
Diff view          | Huge prompt         | N        | N     | UI freeze   | N
Trust threshold    | State lost on restart| N       | N     | Reset ← OK  | N
```

**CRITICAL GAPS: 2** (WASM init, regex divergence)

## Completion Summary

```
+====================================================================+
|            MEGA PLAN REVIEW — COMPLETION SUMMARY                   |
+====================================================================+
| Mode selected        | SELECTIVE EXPANSION                         |
| System Audit         | Bridge scaffolding, 3 TODOs in daemon       |
| Step 0               | Browser-First approach, 3 expansions accepted|
| Section 1  (Arch)    | 1 issue (dual engine parity)                |
| Section 2  (Errors)  | 6 error paths mapped, 3 GAPS                |
| Section 3  (Security)| 1 issue (prompt injection via compression)   |
| Section 4  (Data/UX) | 6 edge cases mapped, 4 unhandled            |
| Section 5  (Quality) | 2 issues (DRY, TODO scaffolding)            |
| Section 6  (Tests)   | Diagram produced, 5 gaps                    |
| Section 7  (Perf)    | 1 issue (WASM dict size)                    |
| Section 8  (Observ)  | 3 gaps (parity monitoring, undo rate, WASM) |
| Section 9  (Deploy)  | 0 risks flagged                             |
| Section 10 (Future)  | Reversibility: 4/5, debt items: 1           |
| Section 11 (Design)  | 3 missing states                            |
+--------------------------------------------------------------------+
| NOT in scope         | written (6 items)                           |
| What already exists  | written                                     |
| Dream state delta    | written                                     |
| Error/rescue registry| 6 methods, 3 CRITICAL GAPS                  |
| Failure modes        | 5 total, 2 CRITICAL GAPS                    |
| TODOS.md updates     | 3 items proposed                            |
| Scope proposals      | 5 proposed, 3 accepted                      |
| CEO plan             | written                                     |
| Outside voice        | ran (codex + subagent)                       |
| Lake Score           | 8/10 chose complete option                  |
| Diagrams produced    | 3 (architecture, data flow, dream state)    |
| Stale diagrams found | 0                                           |
| Unresolved decisions | 0                                           |
+====================================================================+
```

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|---------------|-----------|-----------|----------|
| 1 | CEO | Mode: SELECTIVE EXPANSION | Mechanical | P3 | Feature iteration, not greenfield | EXPANSION, HOLD, REDUCTION |
| 2 | CEO | Approach: Browser-First | Taste | P6+P1 | Fastest validation + completeness. Both models agree current plan order is wrong. | Daemon-First (current plan order) |
| 3 | CEO | Accept E1 (metrics) | Mechanical | P1 | Plan has zero success metrics, always add | Skip |
| 4 | CEO | Accept E2 (hosted proxy) | Mechanical | P4+P6 | Already 80% built, DRY | Skip |
| 5 | CEO | Defer E3 (VS Code) | Mechanical | P3 | Scope too wide, MCP server exists | Accept |
| 6 | CEO | Defer E4 (enterprise) | Mechanical | P3 | Ocean, not lake | Accept |
| 7 | CEO | Accept E5 (competitive benchmark) | Mechanical | P1 | Need to track competitive position | Skip |
| 8 | CEO | Reorder priorities: P3 first | User Challenge | P6 | Both models agree viral channel must ship first | Keep original P1-first order |
| 8R | CEO | USER REJECTED reorder. Keep Daemon-First. | User Decision | — | User wants Grammarly-level integrated experience. One install, everything bootstraps. | Browser-First approach |
| 9 | CEO | Premises accepted as-is | User Decision | — | User accepted all 5 premises as working assumptions | Challenge |
| 10 | Design | Diff view must ship Phase A, not B | Mechanical | P1 | Trust problem exists from compression #1. Both models agree. | Keep diff in Phase B |
| 11 | Design | Extension needs first-run experience | Mechanical | P1 | No onboarding tooltip, no "first time" state for button | Skip |
| 12 | Design | Add extension state machine diagram | Mechanical | P1 | Every state needs: what user sees, can do, how to exit | Skip |
| 13 | Design | Specify diff view rendering concretely | Mechanical | P5 | Word-level diff, inline panel below text field, "Use optimized" button | Leave generic |
| 14 | Eng | Golden-file parity test harness before Rust engine | Mechanical | P1 | Run 500+ inputs through Python, capture outputs, validate Rust matches | Skip |
| 15 | Eng | Fix stats concurrent write race | Mechanical | P5 | Arc<Mutex<Stats>> with periodic flush | Per-request file I/O |
| 16 | Eng | Fix stale-check per-source, not global | Mechanical | P5 | Separate AtomicU64 per RequestSource | Keep global |
| 17 | Eng | Add input size check in extension (64KB) | Mechanical | P5 | Show "Prompt too long" before sending | Let daemon handle |
| 18 | Eng | Add serial_test to flaky daemon tests | Mechanical | P1 | Tests share global state, parallel execution = nondeterministic | Skip |
| 19 | Eng | Clipboard fallback: clear after 3s | Mechanical | P1 | Prevents prompt text leaking to other apps | Keep clipboard leak |
| 20 | Eng | Define native messaging wire protocol schema | Mechanical | P1 | background.js expects "compressed", bridge returns "compiled_text" | Leave undefined |
| 21 | Eng | Resolve Option A vs B before implementation | Mechanical | P5 | Cannot estimate scope with open architecture question | Defer |
| 22 | Eng | Move diff view to Phase A | Taste | P1 | Both design models + eng codex agree. User shipped Daemon-First but diff is independent of daemon. | Keep Phase B |
| 23 | Eng | Add CWS policy validation gate before P4 | Mechanical | P3 | Building auto-compress without policy check = potential rework | Build then check |
| 24 | DX | Define success metrics: activation, undo rate, retention, semantic regression | Mechanical | P1 | Plan has zero metrics, expansion E1 accepted | Skip metrics |
| 25 | DX | Add version negotiation between extension and daemon | Mechanical | P1 | Codex flagged: no protocol versioning, capability negotiation, or downgrade | Skip versioning |

---

# PHASE 2: DESIGN REVIEW

## CLAUDE SUBAGENT (design, independent review)

14 findings (4 CRITICAL, 6 HIGH, 4 MEDIUM):

**CRITICAL:**
1. No first-run experience for extension. User sees "Optimize" button with no context.
2. Diff view in Phase B but trust problem starts at compression #1. Shipping compression without diff = shipping anxiety.
3. Daemon-offline + WASM-not-loaded dead zone. Button exists but clicking does nothing.
4. Diff view has zero rendering spec (algorithm, container, dismiss, accept action all undefined).

**HIGH:**
5. No extension onboarding despite being first impression.
6. Multiple editable fields, no visual binding between button and target field.
7. Popup on unsupported site shows confusing state.
8. Three inconsistent framings: "faster response" / "Optimize" / "compression."
9. Auto-compress intercept UX completely unspecified.
10. Trust threshold persistence unspecified (where, reset, per-site vs global).

**MEDIUM:**
11. All new UI elements position-collide in bottom-right.
12. WASM-to-daemon mid-session transition undefined.
13. Undo lost on SPA navigation, no indication.
14. Notification toast positioned far from user attention.

## CODEX SAYS (design, UX challenge)

Verdict: plan is developer-first, not user-first.
- Information hierarchy serves implementers > users.
- Interaction states claimed but then immediately marked missing (contradiction).
- Responsive strategy absent (no breakpoints, no mobile, no touch).
- Accessibility aspirational (no keyboard flows, ARIA, contrast, touch targets).
- UI decisions are generic patterns ("toast", "split view") without specs.
- Silent semantic corruption from regex divergence is UX debt, not just eng bug.
- CEO findings (metrics, kill criteria) still unresolved in UI terms.

## DESIGN DUAL VOICES, CONSENSUS TABLE

```
DESIGN DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Info hierarchy serves user?       NO      NO     CONFIRMED: developer-first
  2. Missing states specified?         NO      NO     CONFIRMED: incomplete
  3. User journey breaks where?        Step 5  Step 1 CONFIRMED: trust is the gap
  4. UI decisions specific?            NO      NO     CONFIRMED: generic patterns
  5. Diff view timing right?           NO      NO     CONFIRMED: must be Phase A
  6. Accessibility specified?          NO      NO     CONFIRMED: aspirational only
  7. Responsive strategy?              NO      NO     CONFIRMED: absent
═══════════════════════════════════════════════════════════════
7/7 CONFIRMED. 0 DISAGREE.
```

**Phase 2 complete.** Codex: 7 concerns. Claude subagent: 14 issues. Consensus: 7/7 confirmed. Passing to Phase 3.

---

# PHASE 3: ENG REVIEW

## CLAUDE SUBAGENT (eng, independent review)

19 findings (2 CRITICAL, 9 HIGH, 6 MEDIUM, 2 LOW):

**CRITICAL:**
1. Dual-engine parity underestimated. Python engine has 100+ regex patterns, escape sentinels, negation-aware matching. Porting to byte-identical Rust is multi-month, not 2-3 weeks.
2. ProseMirror write-back untested and fragile. Works today via synthetic paste + DataTransfer but relies on framework internals.

**HIGH:**
3. Stats file concurrent write race (pipeline.rs:72-79, no locking).
4. Stale-check discards valid cross-source requests (pipeline.rs:31, global not per-source).
5. No input size limit in extension before sending to daemon.
6. Global static state causes flaky tests (DEGRADED, INITIALIZED, LATEST_REQUEST_ID).
7. Zero extension tests (background.js, content.js).
8. Clipboard fallback leaks prompt text.
9. SymSpell dictionary (30MB) blocks WASM plan.

**MEDIUM:**
10. Native messaging wire protocol undefined (field name mismatch).
11. Queue drop-oldest documented but drop-newest implemented.
12. Orphaned spawn_blocking tasks under load.
13. pendingRequests leak on failed reconnect.
14. No sender validation in background.js.
15. No input sanitization before bridge.

**Architecture diagram:**
```
Extension (content.js)
    │
    ├──[WASM path]──▶ Rust/WASM Engine (new)
    │                    ├── spell (symspell crate)
    │                    ├── patterns (regex)
    │                    ├── filler removal
    │                    └── structure cleanup
    │
    └──[daemon path]──▶ background.js ──▶ Native Messaging
                                              │
                                         Rust Daemon
                                              │
                                         ┌────┴────┐
                                         │ queue.rs │
                                         │ pipeline │
                                         │ bridge   │
                                         └────┬────┘
                                              │ PyO3 / python-build-standalone
                                         Python Engine
                                              ├── alchemist.py
                                              ├── spell.py
                                              └── alchemist_prime.py
```

**Test diagram:**
```
NEW UX FLOWS:                          TEST TYPE    EXISTS?  GAP?
─────────────────────────────────────  ──────────── ──────── ─────
WASM fallback compression              Unit+E2E     NO       YES
Diff view (before/after)               Unit+E2E     NO       YES
Auto-compress on submit                E2E          NO       YES
Onboarding wizard steps                Unit+E2E     NO       YES
Trust threshold transition             Unit         NO       YES

NEW DATA FLOWS:
─────────────────────────────────────
Text → WASM → compressed              Unit         NO       YES
Text → diff renderer → side-by-side   Unit         NO       YES
Parity: Python output == Rust output   Integration  NO       YES ← CRITICAL

NEW ERROR/RESCUE PATHS:
─────────────────────────────────────
WASM init failure → "unavailable"      Unit         NO       YES
WASM OOM → passthrough                 Unit         NO       YES
Submit intercept race → guard          Unit         NO       YES
Stats file corruption → default        Unit         NO       YES
Wire protocol mismatch → error         Integration  NO       YES
```

## CODEX SAYS (eng, architecture challenge)

5 CRITICAL, 5 HIGH, 1 MEDIUM:

1. **CRITICAL:** Plan has mutually incompatible execution paths (Daemon-First in phases, Browser-First in review body). Not executable as written.
2. **CRITICAL:** Option A vs B still open but downstream sections assume Rust canonical + Python reference.
3. **CRITICAL:** "Unresolved decisions: 0" while open questions still exist.
4. **CRITICAL:** Success metrics accepted as expansion E1 but still not defined.
5. **CRITICAL:** Diff view still Phase B despite internal requirement for Phase A.
6. **HIGH:** Multi-engine version skew management missing (protocol versioning, capability negotiation).
7. **HIGH:** CWS policy risk has no pre-commit validation gate.
8. **HIGH:** Onboarding missing hard cases (denied permissions, multi-profile Chrome, partial completion).
9. **HIGH:** "No PII" conflicts with proposed observability (undo tracking, fallback rates).
10. **HIGH:** State modeling incomplete, no deterministic transitions or recovery paths.

## ENG DUAL VOICES, CONSENSUS TABLE

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               ISSUES  ISSUES CONFIRMED: parity + race bugs
  2. Test coverage sufficient?         NO      NO     CONFIRMED: zero extension tests
  3. Performance risks addressed?      PARTIAL PARTIAL CONFIRMED: WASM dict, sync I/O
  4. Security threats covered?         PARTIAL NO     CONFIRMED: clipboard leak, PII
  5. Error paths handled?              NO      NO     CONFIRMED: wire protocol, WASM
  6. Deployment risk manageable?       YES     NO     DISAGREE: Codex says plan
                                                      not executable as-is
═══════════════════════════════════════════════════════════════
5/6 CONFIRMED. 1 DISAGREE (surfaced at gate).
```

**Phase 3 complete.** Codex: 10 concerns. Claude subagent: 19 issues. Consensus: 5/6 confirmed, 1 disagreement. Passing to Phase 3.5.

---

# PHASE 3.5: DX REVIEW

AlienTalk IS a developer tool. DX is the product.

## Developer Journey Map

| Stage | Current State | Target State |
|-------|--------------|-------------|
| 1. Discover | GitHub README, 7 integration methods | 3 clear entry points |
| 2. Evaluate | Clone repo, read README | See savings demo on landing page |
| 3. Install (extension) | Sideload from chrome://extensions | CWS one-click install |
| 4. Install (daemon) | Build from source (Rust + Python) | .dmg drag-to-Applications |
| 5. First value | Click Optimize button, see % | Auto-compression on first prompt |
| 6. Configure | Edit ~/.alientalk/config.json | Settings in menu bar popover |
| 7. Debug | Read daemon logs | "Status: Active" in tray + extension popup |
| 8. Upgrade | git pull + rebuild | Sparkle auto-update |
| 9. Extend | Fork + modify Python engine | MCP server + SDK wrapper |

**TTHW (Time to Hello World):**
- Current: ~30 min (clone, install Python deps, install Rust, cargo build, sideload extension)
- Target (Phase A): ~2 min (download .dmg, drag to Applications, grant permissions, CWS install)
- Target (Phase B with WASM): ~30 sec (CWS install, done)

## Developer Empathy Narrative

"I heard about AlienTalk on Twitter. Someone said it makes Claude respond faster. I go to the Chrome Web Store, install the extension. I open claude.ai. There's a small button near the text field that says 'Optimize.' I type my usual prompt, click it, and see '34% faster response.' Cool. I click undo to check... yep, same meaning. After a few days I stop clicking undo. After a week I forget it's there. My prompts are just better."

That's the dream. The gap: steps 3-5 currently require a separately installed Rust daemon. Until P1 ships, there's no path from discovery to value in under 30 minutes.

## DX Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| 1. Getting started | 3/10 | Requires Rust + Python + sideloading. No pre-built binary. |
| 2. API/CLI naming | 7/10 | `PromptCompiler.compile()`, `estimate_savings()` are guessable. |
| 3. Error messages | 5/10 | Extension: good (`humanError`). Daemon: tracing only, no user-facing errors. |
| 4. Documentation | 6/10 | README covers 7 methods but too dense. Missing quickstart per audience. |
| 5. Upgrade path | 2/10 | No auto-update. No versioning. No migration guides. |
| 6. Dev environment | 4/10 | Rust + Python + Chrome + macOS. Four toolchains to set up. |
| 7. Escape hatches | 8/10 | Undo button, passthrough on error, mode selection in config. |
| 8. Extensibility | 7/10 | MCP server, SDK wrapper, proxy. Good primitives. |
| **Overall** | **5.3/10** | |

## DX Implementation Checklist

- [ ] Pre-built .dmg with bundled Python (P1) — TTHW from 30min to 2min
- [ ] CWS listing (P2) — one-click extension install
- [ ] Quickstart README per audience: chat users, power users, developers
- [ ] Error messages with problem + cause + fix in daemon
- [ ] Sparkle auto-update framework in daemon
- [ ] Version number in extension popup + daemon tray
- [ ] `--version` flag for CLI tools (repl.py, pipe.sh)

## PHASE 3.5 SUMMARY

DX overall: 5.3/10. TTHW: 30 min → 2 min (Phase A target). The biggest DX gap is the install friction the entire plan exists to solve. Plan priorities are correctly ordered for DX improvement. The missing pieces are: per-audience quickstart docs, error message quality in daemon, and auto-update infrastructure.

---

# CROSS-PHASE THEMES

Three concerns appeared in 2+ phases independently. High-confidence signals.

**Theme 1: Diff view timing.** Flagged in Phase 1 (CEO: both models), Phase 2 (Design: both models), Phase 3 (Eng: Codex). The diff view is the trust mechanism. Trust must exist before silent compression. Diff in Phase B while compression ships Phase A = shipping anxiety. **4/4 voices agree. This is the strongest signal in the entire review.**

**Theme 2: Plan self-contradictions.** Phase 3 (Eng: Codex) flagged mutually incompatible paths (Daemon-First phases vs Browser-First review body). Phase 1 (CEO: both) flagged unresolved Option A vs B. The plan file says "Unresolved decisions: 0" but has 4 open questions. The plan needs a cleanup pass to resolve contradictions before implementation.

**Theme 3: Success metrics.** Phase 1 (CEO: both), Phase 2 (Design: Codex), Phase 3 (Eng: Codex), Phase 3.5 (DX). Every phase flagged the absence of measurable success criteria. Expansion E1 was accepted but metrics still don't exist in the plan.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | ISSUES OPEN (via /autoplan) | 3 critical gaps |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | ISSUES OPEN (via /autoplan) | 19 issues, 2 critical |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | ISSUES OPEN (via /autoplan) | 14 issues, 4 critical |
| DX Review | `/plan-devex-review` | Developer experience | 1 | ISSUES OPEN (via /autoplan) | 5.3/10 overall |
| Dual Voices (CEO) | `/autoplan` | Cross-model consensus | 1 | codex+subagent | 5/6 confirmed |
| Dual Voices (Design) | `/autoplan` | Cross-model consensus | 1 | codex+subagent | 7/7 confirmed |
| Dual Voices (Eng) | `/autoplan` | Cross-model consensus | 1 | codex+subagent | 5/6 confirmed |

**VERDICT:** REVIEWED. All 4 phases complete. 25 decisions logged. User approved with Option B (Rust rewrite) and diff view in Phase A.
