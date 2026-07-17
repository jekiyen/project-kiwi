# Kiwi Autofill (browser extension MVP)

Assisted autofill for job application forms, using your Project Kiwi
Application Profile, Active Resume, and (when available) your generated
Cover Letter. **Kiwi assists — you always review and submit manually.**
This extension never clicks Submit, never bypasses CAPTCHA or a login wall,
and never stores any Kiwi data or third-party credentials itself.

## Architecture

```
Generic Form Detector   (content/content-script.js)
        ↓
Field Mapping Engine    (lib/field-mapping.js — deterministic, no AI)
        ↓
Kiwi Profile Data       (background/service-worker.js → GET /application-profile/, /resumes/)
        ↓
Safe Autofill           (content/content-script.js — fill, or annotate for review)
```

A **site-specific adapter** layer is stubbed (`SITE_ADAPTERS` in
`content-script.js`) but empty in this MVP — the generic detector is the
whole story for now. Adapters for particular sites can be added later
without changing the generic path.

### Why a browser extension at all?

Kiwi's web app runs at `localhost:5173` and cannot reach into a page served
from `seek.co.nz` or `nz.indeed.com` — that's an ordinary, correct browser
security boundary (cross-origin script access is blocked). A browser
extension is the standard, supported way to act across origins on the
user's behalf, which is why this MVP is architected as one rather than as
a web-app feature.

### Data access & security

Kiwi has **no authentication** (it's a single-user, local-only tool — see
`CLAUDE.md`), so there are no credentials of any kind to store in the
extension. The background service worker fetches `http://localhost:8000`
directly using the `host_permissions` grant in `manifest.json`; MV3
background workers are privileged and can fetch a permitted origin without
being subject to that origin's CORS policy, so no backend CORS changes were
needed for this. **Content scripts never fetch Kiwi directly** — they only
talk to the background worker via `chrome.runtime.sendMessage`, keeping all
network access in one small, auditable file.

Nothing is sent to any third-party or AI service. Field mapping is 100%
deterministic keyword/attribute matching (`lib/field-mapping.js`) — no paid
API, no network call beyond the user's own local Kiwi backend.

## Supported fields (MVP)

**Personal:** Full Name, First Name, Last Name, Preferred Name, Email,
Phone, Current Address, City, Country, Nationality.

**Work Rights:** Current Country, Visa Status, Eligible to Work in NZ, Need
Sponsorship, Driver License, Own Vehicle.

**Professional:** LinkedIn, Portfolio, GitHub, Website.

**Application assets:** Active Resume and generated Cover Letter are
*detected and annotated*, never auto-filled — see "File upload limitation"
below.

## Install (Chrome / Chromium, developer mode)

1. Make sure the Kiwi backend is running locally (`uvicorn backend.main:app --reload`, default `http://localhost:8000`).
2. Open `chrome://extensions`.
3. Turn on **Developer mode** (top-right toggle).
4. Click **Load unpacked** and select this `extension/` folder.
5. Pin the "Kiwi Autofill" icon to the toolbar (puzzle-piece icon → pin).

No build step — the extension is loaded directly from these plain
JS/HTML/CSS files.

## Testing the complete flow manually

1. **Kiwi → Launch → exact listing:** In Kiwi, open a job's *Apply* tab and
   click **Launch Application**. If the stored listing URL is exact, it
   opens in a new tab; the Application Session starts/resumes exactly as
   before this milestone.
2. **Apply → Kiwi Autofill:** On the new tab (the employer/job-board
   application form), click the Kiwi Autofill toolbar icon.
   - If Kiwi's backend isn't reachable, the popup says so.
   - If no form fields are detected, the popup says so.
   - Otherwise, click **Fill Application**.
3. **Review:** Filled fields get a solid green outline; fields Kiwi wasn't
   confident enough to fill get a dashed amber outline (hover for a hint on
   asset fields); everything else is untouched. The popup shows counts:
   *N fields filled*, *M need review*, *K could not be matched*.
4. **Manual Submit:** You review and submit the form yourself — the
   extension has no code path that clicks Submit/Send/Confirm/Apply.
5. **Return to Kiwi → confirm:** Back in Kiwi's Apply tab, answer "Did you
   successfully submit this application?" (Applied / Not Yet / Cancelled /
   Listing Unavailable) exactly as before.

For a controlled test without a real job site, open
`extension/test-page/sample-form.html` directly in Chrome and run the same
Fill Application flow against it — it includes a pre-filled field (must not
be overwritten), an unmappable field (must stay untouched), and a Submit
button wired to visibly alert if it's ever triggered programmatically.

## File upload limitation

Browsers block programmatic population of `<input type="file">` for
security reasons, and this extension does not attempt to work around that.
For Resume and Cover Letter file inputs, Kiwi Autofill detects the field
and gives you a hint (which document/version to use) via a hover tooltip
on the highlighted field — the actual file selection stays entirely
user-controlled through the browser's native file picker.

## Known limitations

- **Cover letter text isn't stored in Kiwi at all.** Kiwi's architecture
  deliberately never persists AI-generated text (see `docs/ROADMAP.md`
  Phase 7.4) — a cover letter is written by pasting a Kiwi-generated prompt
  into Claude by hand, and the result only ever lives in that conversation.
  This extension therefore cannot autofill actual cover letter *content*;
  it can only detect the field and remind you where to find/generate it.
  Fully solving this would mean changing Kiwi's core "never store AI
  output" principle, which is out of scope for this milestone.
- **Radio button groups and boolean-mapped `<select>` fields are always
  flagged "needs review," never auto-filled.** Reliably picking the correct
  option among arbitrary site-specific labels (e.g. which radio is "Yes")
  is not safe to guess deterministically; this is a deliberate confidence
  cutoff, not a bug.
- **No site-specific adapters ship yet.** Sites with unusual custom form
  widgets (date pickers, multi-step wizards, custom dropdown components
  that aren't real `<select>` elements) may detect fewer fields than a
  standard HTML form. The adapter layer exists precisely so these can be
  addressed incrementally without touching the generic detector.
- **Single-page-app forms that mount fields after `document_idle`** (rare,
  but some heavily client-rendered application flows do this) may not be
  detected on first popup open — reloading the popup after the form has
  fully rendered resolves this.
- **Firefox/Safari are not targeted in this MVP** (Chromium-compatible
  browsers only, per this milestone's scope).
- **"Current Job Context"** (which specific Kiwi job you're applying for)
  only flows through if you clicked Launch Application from Kiwi's Apply
  tab in the same browser session — opening a job site directly (without
  going through Kiwi first) means the cover-letter hint won't know which
  job you're working on.
