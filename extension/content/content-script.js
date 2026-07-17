/**
 * Kiwi Autofill — Content Script.
 *
 * Runs on every page (except Kiwi's own frontend — see kiwi-detect.js) but
 * does NOTHING until the user explicitly triggers it from the popup. This
 * is the "Generic Form Detector" + "Safe Autofill" stages of the
 * architecture described in extension/README.md; field scoring lives in
 * lib/field-mapping.js (loaded before this file — see manifest.json).
 *
 * Hard rules enforced throughout this file:
 *   - Never click or submit anything (no `.click()`/`.submit()` calls exist
 *     in this file at all, and only text/select/checkbox inputs are ever
 *     touched — see CANDIDATE_SELECTOR below).
 *   - Never overwrite a field that already has content unless the user
 *     explicitly re-runs "Fill Application."
 *   - Never fill a file input (browsers block programmatic file selection
 *     for security reasons) — file inputs are only annotated.
 */
(function () {
  "use strict";

  const KIWI_FILLED_ATTR = "data-kiwi-fill-value";

  const CANDIDATE_SELECTOR = [
    "input[type=text]", "input[type=email]", "input[type=tel]",
    "input[type=url]", "input:not([type])", "textarea", "select",
    "input[type=checkbox]", "input[type=radio]", "input[type=file]",
  ].join(",");

  // ── Site-specific adapter hook (future layer — see README) ────────────────
  // No real adapters ship in this MVP; hostname-matched adapters can be
  // registered here later without changing the generic detector below.
  const SITE_ADAPTERS = [];

  function getSiteAdapter() {
    return SITE_ADAPTERS.find((a) => a.matches(window.location.hostname)) || null;
  }

  // ── Label resolution ─────────────────────────────────────────────────────

  function findLabelText(el) {
    if (el.id) {
      const forLabel = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (forLabel) return forLabel.textContent;
    }
    const wrappingLabel = el.closest("label");
    if (wrappingLabel) return wrappingLabel.textContent;

    const ariaLabelledBy = el.getAttribute("aria-labelledby");
    if (ariaLabelledBy) {
      const parts = ariaLabelledBy
        .split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent || "")
        .filter(Boolean);
      if (parts.length) return parts.join(" ");
    }

    // Fall back to the nearest preceding text node within the same
    // container — a common pattern on employer-hosted forms with no real
    // <label> markup at all.
    const container = el.closest("div,li,tr,fieldset") || el.parentElement;
    if (container) {
      const text = container.textContent || "";
      if (text.trim().length < 200) return text;
    }
    return "";
  }

  function isVisible(el) {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  }

  // ── Detection ─────────────────────────────────────────────────────────────

  function detectCandidates() {
    const adapter = getSiteAdapter();
    const root = (adapter && adapter.findFormRoot(document)) || document;

    const elements = Array.from(root.querySelectorAll(CANDIDATE_SELECTOR)).filter(
      (el) => !el.disabled && !el.readOnly && isVisible(el),
    );

    return elements.map((el) => {
      const label = findLabelText(el);
      const match = window.KiwiFieldMapping.matchField(el, label);
      return { el, match };
    });
  }

  // ── Safe fill ─────────────────────────────────────────────────────────────

  function dispatchInputEvents(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function currentValue(el) {
    if (el.type === "checkbox") return el.checked;
    return el.value;
  }

  /** True if this field is safe to (re)write: either Kiwi has never touched
   * it, or the value on the page is still exactly what Kiwi wrote last time
   * (i.e. the user hasn't hand-edited it since). Never overwrites genuine
   * user-entered content. */
  function safeToWrite(el, forceRefill) {
    const priorFillValue = el.getAttribute(KIWI_FILLED_ATTR);
    const existing = currentValue(el);
    const isEmpty = el.type === "checkbox" ? existing === false : !existing;

    if (isEmpty) return true;
    if (!forceRefill) return false;
    // Re-triggered: only overwrite what Kiwi itself last wrote.
    if (priorFillValue === null) return false;
    return String(existing) === priorFillValue;
  }

  function fillTextLike(el, value) {
    el.value = value;
    el.setAttribute(KIWI_FILLED_ATTR, value);
    dispatchInputEvents(el);
  }

  function fillCheckbox(el, boolValue) {
    el.checked = Boolean(boolValue);
    el.setAttribute(KIWI_FILLED_ATTR, String(el.checked));
    dispatchInputEvents(el);
  }

  /** For <select> elements: only fill if some option's text/value
   * confidently contains (or is contained by) the profile value — never
   * guess between ambiguous options. */
  function fillSelect(el, value) {
    const target = window.KiwiFieldMapping.normalize(value);
    if (!target) return false;
    const options = Array.from(el.options);
    const match = options.find((opt) => {
      const optText = window.KiwiFieldMapping.normalize(opt.textContent);
      const optValue = window.KiwiFieldMapping.normalize(opt.value);
      return optText === target || optValue === target || optText.includes(target) || target.includes(optText);
    });
    if (!match) return false;
    el.value = match.value;
    el.setAttribute(KIWI_FILLED_ATTR, match.value);
    dispatchInputEvents(el);
    return true;
  }

  function markHighlight(el, state) {
    el.classList.remove("kiwi-filled", "kiwi-review");
    if (state === "filled") el.classList.add("kiwi-filled");
    if (state === "review") el.classList.add("kiwi-review");
  }

  /** Resolves an Application Profile field key (plus the two derived
   * first_name/last_name keys) to the value that should be written. */
  function resolveValue(key, profile) {
    if (key === "first_name") return (profile.full_name || "").split(/\s+/)[0] || "";
    if (key === "last_name") {
      const parts = (profile.full_name || "").trim().split(/\s+/);
      return parts.length > 1 ? parts.slice(1).join(" ") : "";
    }
    return profile[key];
  }

  function runAutofill(profileData, forceRefill) {
    const { profile, activeResume, jobContext } = profileData;
    const coverLetterGeneratedAt = jobContext && jobContext.coverLetterGeneratedAt;
    const candidates = detectCandidates();

    let filled = 0;
    let review = 0;
    let unmapped = 0;

    for (const { el, match } of candidates) {
      if (!match) {
        unmapped++;
        continue;
      }

      // Resume / cover letter — file inputs can never be programmatically
      // populated (browser security). Annotate, never attempt to fill.
      if (match.isAsset) {
        review++;
        markHighlight(el, "review");
        const jobTitle = jobContext && jobContext.jobTitle;
        el.setAttribute(
          "data-kiwi-hint",
          match.key === "resume_upload"
            ? `Upload your active resume: ${activeResume ? activeResume.filename : "no active resume set in Kiwi"}`
            : coverLetterGeneratedAt
              ? `Paste the cover letter you generated in Kiwi's AI Workspace${jobTitle ? ` for "${jobTitle}"` : ""}`
              : "No cover letter generated yet in Kiwi — visit the AI Workspace tab first",
        );
        continue;
      }

      const rawValue = resolveValue(match.key, profile);
      const isBooleanField = match.fieldType === "boolean";
      const hasValue = isBooleanField ? typeof rawValue === "boolean" : !!rawValue;

      if (match.confidence !== "fill" || !hasValue) {
        review++;
        markHighlight(el, "review");
        continue;
      }

      if (el.tagName.toLowerCase() === "select") {
        if (!safeToWrite(el, forceRefill)) {
          review++;
          markHighlight(el, "review");
          continue;
        }
        const ok = fillSelect(el, String(rawValue));
        if (ok) {
          filled++;
          markHighlight(el, "filled");
        } else {
          review++;
          markHighlight(el, "review");
        }
        continue;
      }

      if (el.type === "checkbox") {
        if (!isBooleanField) {
          review++;
          markHighlight(el, "review");
          continue;
        }
        if (!safeToWrite(el, forceRefill)) {
          review++;
          markHighlight(el, "review");
          continue;
        }
        fillCheckbox(el, rawValue);
        filled++;
        markHighlight(el, "filled");
        continue;
      }

      if (el.type === "radio") {
        // Safely picking the right option among an unknown-labelled radio
        // group is not reliable enough for the MVP's "clear confidence"
        // bar — flag for manual review instead of guessing.
        review++;
        markHighlight(el, "review");
        continue;
      }

      // Plain text-like input / textarea.
      if (!safeToWrite(el, forceRefill)) {
        review++;
        markHighlight(el, "review");
        continue;
      }
      fillTextLike(el, String(rawValue));
      filled++;
      markHighlight(el, "filled");
    }

    return { filled, review, unmapped, total: candidates.length };
  }

  // ── Message handling ──────────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === "DETECT_FORM") {
      const candidates = detectCandidates();
      sendResponse({ fieldCount: candidates.length });
      return true;
    }

    if (message.type === "FILL_APPLICATION") {
      chrome.runtime.sendMessage({ type: "GET_PROFILE_DATA" }, (profileData) => {
        if (chrome.runtime.lastError || !profileData || profileData.error) {
          sendResponse({
            error: (profileData && profileData.error) || "Couldn't reach Kiwi. Is the backend running at localhost:8000?",
          });
          return;
        }
        const result = runAutofill(profileData, !!message.forceRefill);
        sendResponse(result);
      });
      return true; // keep the message channel open for the async response
    }

    return false;
  });
})();
