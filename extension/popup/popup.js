/**
 * Kiwi Autofill — Popup.
 *
 * Deliberately thin: the popup only orchestrates two things the user asks
 * for — "is there a form here?" and "fill it." It never runs anything
 * automatically on page load (see manifest.json — the content script does
 * nothing until this popup messages it).
 */
(function () {
  "use strict";

  const statusEl = document.getElementById("status");
  const appEl = document.getElementById("app");
  const dotEl = document.getElementById("kiwi-status-dot");
  const kiwiStatusText = document.getElementById("kiwi-status-text");

  function setKiwiStatus(state, text) {
    dotEl.className = `dot dot-${state}`;
    kiwiStatusText.textContent = text;
  }

  function renderMessage(text, isError) {
    appEl.innerHTML = "";
    const p = document.createElement("p");
    p.className = isError ? "status error" : "status";
    p.textContent = text;
    appEl.appendChild(p);
  }

  function renderReadyToFill(fieldCount) {
    appEl.innerHTML = "";
    const p = document.createElement("p");
    p.className = "status";
    p.textContent = `Application form detected — ${fieldCount} field${fieldCount === 1 ? "" : "s"} found.`;
    appEl.appendChild(p);

    const btn = document.createElement("button");
    btn.className = "primary";
    btn.textContent = "Fill Application";
    btn.addEventListener("click", () => runFill(false));
    appEl.appendChild(btn);
  }

  function renderSummary(result) {
    appEl.innerHTML = "";

    const summary = document.createElement("div");
    summary.className = "summary";
    summary.innerHTML = `
      <div class="summary-row filled"><span>Fields filled</span><span class="count">${result.filled}</span></div>
      <div class="summary-row review"><span>Need review</span><span class="count">${result.review}</span></div>
      <div class="summary-row unmapped"><span>Could not be matched</span><span class="count">${result.unmapped}</span></div>
    `;
    appEl.appendChild(summary);

    const hint = document.createElement("p");
    hint.className = "status";
    hint.style.marginTop = "10px";
    hint.textContent = "Review the highlighted fields on the page, then submit the form yourself.";
    appEl.appendChild(hint);

    const refillBtn = document.createElement("button");
    refillBtn.className = "secondary";
    refillBtn.textContent = "Fill Again";
    refillBtn.addEventListener("click", () => runFill(true));
    appEl.appendChild(refillBtn);
  }

  function withActiveTab(callback) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (!tab || !tab.id) {
        renderMessage("Couldn't access the current tab.", true);
        return;
      }
      callback(tab.id);
    });
  }

  function runFill(forceRefill) {
    withActiveTab((tabId) => {
      renderMessage("Filling…");
      chrome.tabs.sendMessage(tabId, { type: "FILL_APPLICATION", forceRefill }, (result) => {
        if (chrome.runtime.lastError || !result) {
          renderMessage("Couldn't fill this page — try reloading it and reopening Kiwi Autofill.", true);
          return;
        }
        if (result.error) {
          renderMessage(result.error, true);
          return;
        }
        renderSummary(result);
      });
    });
  }

  function checkKiwiConnection() {
    chrome.runtime.sendMessage({ type: "GET_PROFILE_DATA" }, (data) => {
      if (chrome.runtime.lastError || !data || data.error) {
        setKiwiStatus("danger", "Kiwi backend: not reachable (is it running at localhost:8000?)");
        return;
      }
      setKiwiStatus("success", "Kiwi backend: connected");
    });
  }

  function checkFormOnPage() {
    withActiveTab((tabId) => {
      chrome.tabs.sendMessage(tabId, { type: "DETECT_FORM" }, (response) => {
        if (chrome.runtime.lastError || !response) {
          renderMessage("No application form detected on this page.");
          return;
        }
        if (response.fieldCount === 0) {
          renderMessage("No application form detected on this page.");
          return;
        }
        renderReadyToFill(response.fieldCount);
      });
    });
  }

  checkKiwiConnection();
  checkFormOnPage();
})();
