// Sharp Onboarding — step navigation + Tauri invoke calls

let currentStep = 1;
const totalSteps = 3;

/**
 * Navigate to a specific step.
 */
function goToStep(step) {
  if (step < 1 || step > totalSteps) return;

  // Hide current step
  const current = document.getElementById(`step-${currentStep}`);
  if (current) current.classList.remove("active");

  // Show target step
  const target = document.getElementById(`step-${step}`);
  if (target) target.classList.add("active");

  // Update progress dots
  document.querySelectorAll(".dot").forEach((dot) => {
    const dotStep = parseInt(dot.dataset.step, 10);
    dot.classList.remove("active", "done");
    if (dotStep === step) {
      dot.classList.add("active");
    } else if (dotStep < step) {
      dot.classList.add("done");
    }
  });

  currentStep = step;
}

/**
 * Test compression via Tauri invoke.
 */
async function testCompress() {
  const input = document.getElementById("test-input");
  const resultArea = document.getElementById("result-area");
  const resultText = document.getElementById("result-text");

  const text = input.value.trim();
  if (!text) return;

  try {
    const result = await window.__TAURI__.core.invoke("test_compress", {
      text: text,
    });
    resultText.textContent = result;
    resultArea.classList.remove("hidden");
  } catch (err) {
    console.error("[Sharp] test_compress error:", err);
    resultText.textContent = "Compression failed. Check that the daemon is running.";
    resultArea.classList.remove("hidden");
  }
}

/**
 * Mark onboarding complete and close window.
 */
async function finishOnboarding() {
  try {
    await window.__TAURI__.core.invoke("mark_onboarding_complete");
  } catch (err) {
    console.error("Failed to mark complete:", err);
  }
  // Close the onboarding window
  try {
    const current = window.__TAURI__.window.getCurrentWindow();
    await current.close();
  } catch (_) {
    window.close();
  }
}

/**
 * Skip onboarding and close window.
 */
async function skipOnboarding() {
  try {
    await window.__TAURI__.core.invoke("mark_onboarding_skipped");
  } catch (err) {
    console.error("Failed to mark skipped:", err);
  }
  try {
    const current = window.__TAURI__.window.getCurrentWindow();
    await current.close();
  } catch (_) {
    window.close();
  }
}

// Wire up buttons (no inline onclick)
document.getElementById("btn-start").addEventListener("click", () => goToStep(2));
document.getElementById("btn-back-1").addEventListener("click", () => goToStep(1));
document.getElementById("btn-next-2").addEventListener("click", () => goToStep(3));
document.getElementById("btn-compress").addEventListener("click", testCompress);
document.getElementById("btn-back-2").addEventListener("click", () => goToStep(2));
document.getElementById("btn-done").addEventListener("click", finishOnboarding);
document.getElementById("btn-skip").addEventListener("click", (e) => {
  e.preventDefault();
  skipOnboarding();
});
