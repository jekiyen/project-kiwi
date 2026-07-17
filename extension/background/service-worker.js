/**
 * Kiwi Autofill — Background Service Worker.
 *
 * The only place in the extension that talks to Kiwi's local backend. Kiwi
 * has no authentication (single-user, local-only tool — see CLAUDE.md), so
 * there are no credentials to store or manage here at all: this just reads
 * the same local API the Kiwi web app itself reads, using the
 * `host_permissions` grant in manifest.json (which lets a MV3 background
 * worker fetch a permitted origin without being subject to the target
 * page's CORS policy). Content scripts never fetch Kiwi directly — they
 * always go through this worker via chrome.runtime.sendMessage, keeping
 * all network access in one privileged, auditable place.
 */

const KIWI_API_BASE = "http://localhost:8000/api/v1";

async function fetchProfileData() {
  const [profileRes, resumesRes] = await Promise.all([
    fetch(`${KIWI_API_BASE}/application-profile/`),
    fetch(`${KIWI_API_BASE}/resumes/`),
  ]);

  if (!profileRes.ok || !resumesRes.ok) {
    throw new Error("Kiwi backend responded with an error.");
  }

  const profile = await profileRes.json();
  const resumes = await resumesRes.json();
  const activeResume = resumes.find((r) => r.is_active) || null;

  const { lastJobContext } = await chrome.storage.local.get("lastJobContext");

  return { profile, activeResume, jobContext: lastJobContext || null };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "GET_PROFILE_DATA") {
    fetchProfileData()
      .then((data) => sendResponse(data))
      .catch((err) => sendResponse({ error: err.message || String(err) }));
    return true; // async response
  }

  if (message.type === "SET_JOB_CONTEXT") {
    chrome.storage.local.set({ lastJobContext: message.context }, () => sendResponse({ ok: true }));
    return true;
  }

  return false;
});
