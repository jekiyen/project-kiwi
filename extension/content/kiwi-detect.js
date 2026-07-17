/**
 * Kiwi Autofill — presence announcement + job context bridge.
 *
 * Runs only on Kiwi's own frontend (see manifest.json content_scripts
 * matches) so the Application Kit can (a) tell the user the extension is
 * installed instead of just linking to install instructions blindly, and
 * (b) hand off which job the user is currently launching an application
 * for, so the extension can give a job-specific cover-letter hint later on
 * the actual application-form tab. No profile data flows through here —
 * only a job id/title/employer and the cover-letter-generated timestamp,
 * all of which are already visible on the page the user is looking at.
 */
(function () {
  "use strict";
  document.documentElement.setAttribute("data-kiwi-extension", "true");
  window.dispatchEvent(new CustomEvent("kiwi-extension-installed"));

  window.addEventListener("kiwi-launch-context", (event) => {
    chrome.runtime.sendMessage({ type: "SET_JOB_CONTEXT", context: event.detail });
  });
})();
