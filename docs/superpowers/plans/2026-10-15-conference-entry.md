# Conference entry implementation plan

**Goal:** Add screenshot-style enrollment/login actions across conference pages using existing authenticated business flows.

**Architecture:** Shared server-rendered Jinja strip; display.py supplies native/external/closed registration; portal.js updates guest/member state; isolated existing account browser fixtures.

- [x] Add a failing complete-rendering assertion for `data-conference-entry` and run it.
- [x] Add shared participation markup/CSS, derive entry from existing actions and native registration, include both templates, preserve configured flags and existing accounts.
- [x] Update portal session refresh for guest login, member participation and native registration URL; keep translations and accessible disabled state.
- [x] Extend existing account UI verification for both themes, column pages, closed enrollment, signed-in states and responsive widths; run account/rendering/LAN regressions and document results.

Completed and reviewed: rendering and expanded real account browser checks pass; no external test email, no live enrollment data changes to22/61.
