# Conference Business Workspace Plan

> Use subagent-driven-development for independent backend, Vue component, and native page skin ownership. Root integrates existing App and navigation then runs real end-to-end checks. Scope follows the already authorized three priorities.

**Goal:** Provide usable organizer registration/submission management and a private participant center in the existing brand.

**Architecture:** Native Indico records and operations, private read-only aggregate APIs, Vue/Element Plus summaries, native-form Jinja shell and scoped CSS. No new business database or payment integrations.

- [x] Backend worker: business.py, blueprint.py, tests/backend/verify_business_workspace.py. Write missing API red first; actual scoped queries/ownership/canonical links/disabled and withdrawn checks; fixture integration with locmem mail.
- [x] Frontend worker: BusinessWorkspace.vue and optional business-workspace.css, tests/browser/verify_business_workspace_ui.cjs. Use exact API contract; missing route/UI red first. Root owns App.vue integration/mode/routes/sidebar. Component receives mode,eventId,language.
- [x] Native-shell worker: plugin __init__.py asset injection, customization/templates/core/events management/display overrides, native-business.css/js, dedicated native test. Preserve native bundle/DOM/confirmation logic; include AJAX fragments unchanged; no source upstream edits. Worker tests selectors before changing pages.
- [x] Root: integrate mode routes template shell through blueprint worker and App.vue, global links/participant sidebar. Build and restart services once coherent. Verify APIs plus actual native registration/submission/approval/export/review with temporary records, and responsive component/native forms screenshots.
- [x] Independent reviewer checks ACL, personal-data isolation, state accuracy, native form behavior and regressions. Fix findings, rerun relevant tests, document completed scope/boundaries and fixture cleanup.

Completed 2026-10-15. Actual registration approval/CSV, abstract review/judgment/contribution creation and participant state synchronization verified with locmem mail. Native browser validation covers15pages and2dialogs at1440/390/320px, review action contrast and preserved native constraints. Independent review findings fixed and covered by regression assertions. Business temporary events/accounts checked at zero active records; meetings22/61 preserved. See ../../conference-business-validation.md for usage, evidence and remaining boundaries.

Workspace has no Git repository; no commits/worktrees. Never read or print credentials/environment config, send external test mail, or modify meetings22/61. User's real SMTP remains configured; native HTTP mutation tests must run in isolated make_app locmem process.
