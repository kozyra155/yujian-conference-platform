# Complete Conference Template Implementation Plan

> **For agentic workers:** Use subagent-driven-development for the independent backend, public rendering, and editor tasks. Shared API contract is the approved design document; do not modify files owned by other workers.

**Goal:** Make the platform create and maintain complete conference websites comparable to UAVRS2026.

**Architecture:** Structured content in plugin event settings with native pages, attachment archive, ACL and business modules. Vue/Element Plus editor plus SSR public presentation; existing templates remain compatible.

**Tech Stack:** Indico 3.3.13 / Flask / PostgreSQL, Vue 3 / Element Plus / Vite, Playwright.

- [x] Backend: added verify_complete_site.py first; the native catchall returned405 for the missing content endpoint (rather than404). Implemented site_content.py, blueprint endpoints, template initialization and secure upload; real Flask integration assertions pass. Own plugin __init__.py, blueprint.py, new site_content.py and backend test.
- [x] Public presentation: regression rendering assertions observed failing before implementation; complete-conference.html/CSS/JS and conditional display.py add recursive ACL navigation, bilingual fields and responsive reference layout. Dedicated renderer and live browser checks pass.
- [x] Editor: browser smoke first failed at absent editor tab; SiteContentEditor.vue and App.vue now default to academic-full while preserving two older options. Real upload/removal, list management, save conflict/errors and unsaved drafts verified in browser.
- [x] Integration: frontend build passed; web/celery/beat restarted, Nginx upload limit validated and reloaded. Complete-site backend/browser tests and relevant legacy regressions pass. Disposable records cleaned, conference22 untouched. Desktop/mobile screenshots inspected; permanent clearly labelled demonstration is event61.
- [x] Independent spec/security/code review: fixed attachment-folder collision, proved red/green regression, re-review passed. README and docs/complete-conference-validation.md record checks and boundaries.

No Git repository exists in this workspace, so commits/worktrees do not apply. Preserve source in the active shared workspace; deployment stays on localhost12880.
