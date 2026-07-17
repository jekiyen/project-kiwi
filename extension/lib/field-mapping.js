/**
 * Kiwi Autofill — Field Mapping Engine.
 *
 * Deterministic, keyword-based mapping from a detected form field to a
 * Kiwi Application Profile key. No AI, no network calls, no paid
 * dependency — see docs/ROADMAP.md "Application Flow Reliability &
 * Assisted Autofill" for why this stays deterministic for the MVP.
 *
 * Architecture (see extension/README.md for the full diagram):
 *   Generic Form Detector -> Field Mapping Engine (this file) -> Kiwi
 *   Profile Data -> Safe Autofill
 *
 * This file only exposes pure functions on `window.KiwiFieldMapping` — it
 * never touches the DOM itself (that's content-script.js's job) and never
 * calls any Kiwi/AI API.
 */
(function () {
  "use strict";

  // Each definition describes one Application Profile field to look for.
  // `keywords` are matched against label text / placeholder / name / id
  // (all lower-cased, punctuation collapsed to spaces). `autocomplete`
  // matches the input's autocomplete attribute exactly. `exclude` keywords
  // disqualify a field entirely (e.g. "first name" must not match "name").
  // `weight` lets a few especially reliable signals (autocomplete, exact
  // name/id match) count for more than a loose label/placeholder match.
  const FIELD_DEFINITIONS = [
    {
      key: "full_name",
      label: "Full Name",
      keywords: ["full name", "fullname", "your name", "applicant name", "candidate name", "name"],
      autocomplete: ["name"],
      exclude: ["first", "last", "middle", "company", "user name", "username", "file"],
    },
    {
      key: "first_name",
      label: "First Name",
      keywords: ["first name", "given name", "firstname", "fname"],
      autocomplete: ["given-name"],
    },
    {
      key: "last_name",
      label: "Last Name",
      keywords: ["last name", "surname", "family name", "lastname", "lname"],
      autocomplete: ["family-name"],
    },
    {
      key: "preferred_name",
      label: "Preferred Name",
      keywords: ["preferred name", "nickname", "known as", "goes by"],
    },
    {
      key: "email",
      label: "Email",
      keywords: ["email", "e-mail"],
      autocomplete: ["email"],
      inputTypes: ["email"],
    },
    {
      key: "phone",
      label: "Phone",
      keywords: ["phone", "mobile", "telephone", "contact number", "cell number"],
      autocomplete: ["tel"],
      inputTypes: ["tel"],
    },
    {
      key: "current_address",
      label: "Current Address",
      keywords: ["address", "street address", "current address", "residential address"],
      autocomplete: ["street-address", "address-line1"],
      exclude: ["email"],
    },
    {
      key: "city",
      label: "City",
      keywords: ["city", "town", "suburb"],
      autocomplete: ["address-level2"],
    },
    {
      key: "country",
      label: "Country",
      keywords: ["country", "country of residence"],
      autocomplete: ["country", "country-name"],
      exclude: ["nationality", "eligib", "visa", "sponsor", "citizenship"],
    },
    {
      key: "nationality",
      label: "Nationality",
      keywords: ["nationality", "citizenship"],
    },
    {
      key: "work_rights_current_country",
      label: "Current Country (Work Rights)",
      keywords: ["current country", "country you are currently", "country currently residing"],
    },
    {
      key: "visa_status",
      label: "Visa Status",
      keywords: ["visa status", "visa type", "work permit", "work visa status"],
    },
    {
      key: "eligible_to_work_nz",
      label: "Eligible to Work in NZ",
      keywords: [
        "eligible to work", "right to work", "legally entitled to work",
        "work rights", "authorised to work", "authorized to work",
      ],
      fieldType: "boolean",
    },
    {
      key: "need_sponsorship",
      label: "Need Sponsorship",
      keywords: ["require sponsorship", "need sponsorship", "visa sponsorship", "sponsorship to work"],
      fieldType: "boolean",
    },
    {
      key: "driver_license",
      label: "Driver License",
      keywords: ["driver licence", "driver's licence", "driver license", "driving licence", "driving license"],
      fieldType: "boolean",
    },
    {
      key: "own_vehicle",
      label: "Own Vehicle",
      keywords: ["own vehicle", "own transport", "own car", "access to a vehicle"],
      fieldType: "boolean",
    },
    {
      key: "linkedin_url",
      label: "LinkedIn",
      keywords: ["linkedin"],
    },
    {
      key: "portfolio_url",
      label: "Portfolio",
      keywords: ["portfolio"],
    },
    {
      key: "github_url",
      label: "GitHub",
      keywords: ["github"],
    },
    {
      key: "website_url",
      label: "Website",
      keywords: ["personal website", "personal site", "website", "web site"],
      exclude: ["linkedin", "github", "portfolio"],
    },
  ];

  // Special, non-Profile-field categories detected separately since they
  // can never be safely autofilled (browser security + Kiwi's own
  // architecture — see extension/README.md "Known limitations").
  const ASSET_DEFINITIONS = [
    {
      key: "resume_upload",
      label: "Resume / CV Upload",
      keywords: ["resume", "cv", "curriculum vitae"],
      onlyFileInputs: true,
    },
    {
      key: "cover_letter_upload",
      label: "Cover Letter Upload",
      keywords: ["cover letter", "covering letter"],
      onlyFileInputs: true,
    },
    {
      key: "cover_letter_text",
      label: "Cover Letter",
      keywords: ["cover letter", "covering letter", "why do you want", "tell us about yourself"],
      onlyTextareas: true,
    },
  ];

  const FILL_THRESHOLD = 3; // confident enough to actually write a value
  const REVIEW_THRESHOLD = 1; // some signal, but not confident enough to fill

  function normalize(text) {
    return (text || "")
      .toLowerCase()
      .replace(/[_\-]+/g, " ")
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  /** Collects every text signal a field exposes: label, name, id,
   * placeholder, aria-label, and autocomplete — everything the brief asks
   * detection to consider. */
  function collectFieldText(el, label) {
    return {
      combined: normalize(
        [label, el.name, el.id, el.placeholder, el.getAttribute("aria-label")].join(" "),
      ),
      name: normalize(el.name),
      id: normalize(el.id),
      autocomplete: (el.getAttribute("autocomplete") || "").toLowerCase().trim(),
      inputType: (el.type || "").toLowerCase(),
    };
  }

  function scoreDefinition(def, fieldText) {
    if (def.inputTypes && !def.inputTypes.includes(fieldText.inputType)) {
      // A strong type hint (email/tel) that mismatches is not disqualifying
      // on its own — some sites use type="text" for everything — but it
      // means we lean on keyword matches alone below.
    }

    if (def.exclude && def.exclude.some((kw) => fieldText.combined.includes(kw))) {
      return 0;
    }

    let score = 0;

    if (def.autocomplete && def.autocomplete.includes(fieldText.autocomplete)) {
      score += 4;
    }
    if (def.inputTypes && def.inputTypes.includes(fieldText.inputType)) {
      score += 2;
    }

    // Exact-ish match on name/id (the most deliberate signal a form author
    // gives) counts for more than a fuzzy label/placeholder match.
    for (const kw of def.keywords) {
      const kwNorm = normalize(kw);
      if (fieldText.name === kwNorm.replace(/\s+/g, "") || fieldText.id === kwNorm.replace(/\s+/g, "")) {
        score += 3;
        break;
      }
    }
    for (const kw of def.keywords) {
      if (fieldText.combined.includes(normalize(kw))) {
        score += 2;
        break;
      }
    }

    return score;
  }

  /** Returns the best-matching field definition (Application Profile field
   * or asset upload) for one detected form control, or null if nothing
   * scored above the review threshold ("could not map"). */
  function matchField(el, label) {
    const fieldText = collectFieldText(el, label);
    let best = null;
    let bestScore = 0;

    const isFileInput = fieldText.inputType === "file";
    const isTextarea = el.tagName.toLowerCase() === "textarea";

    for (const def of ASSET_DEFINITIONS) {
      if (def.onlyFileInputs && !isFileInput) continue;
      if (def.onlyTextareas && !isTextarea) continue;
      const score = scoreDefinition(def, fieldText);
      if (score > bestScore) {
        best = def;
        bestScore = score;
      }
    }

    if (!isFileInput) {
      for (const def of FIELD_DEFINITIONS) {
        const score = scoreDefinition(def, fieldText);
        if (score > bestScore) {
          best = def;
          bestScore = score;
        }
      }
    }

    if (!best || bestScore < REVIEW_THRESHOLD) return null;

    return {
      key: best.key,
      label: best.label,
      score: bestScore,
      confidence: bestScore >= FILL_THRESHOLD ? "fill" : "review",
      fieldType: best.fieldType || (isTextarea ? "text" : "text"),
      isAsset: ASSET_DEFINITIONS.includes(best),
    };
  }

  window.KiwiFieldMapping = {
    FIELD_DEFINITIONS,
    ASSET_DEFINITIONS,
    FILL_THRESHOLD,
    REVIEW_THRESHOLD,
    normalize,
    collectFieldText,
    scoreDefinition,
    matchField,
  };
})();
