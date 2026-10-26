# Appearance Presets Implementation Plan

> Use subagent-driven-development for independent backend and editor work, while root owns SSR layout/CSS integration. User authorized implementation; no additional design gate.

**Goal:** Add twelve reusable selectable conference appearances matching the supplied two-layout/six-color reference.

**Architecture:** Existing structured content and revision save; theme.layout plus accent. Shared server catalog, private no-write preview endpoint, existing SSR with layout classes, Vue picker. No new dependencies or third-party runtime.

- [x] Backend: appearances.py, compatible theme.layout/defaults, shared strict validation, content catalog and private preview POST implemented. Missing-catalog test observed red; actual API suite now passes12 saves/no-write preview/ACL/CSRF/lock.
- [x] Editor: AppearancePicker.vue with two groups×six code thumbnails, native radios, actual saved-content iframe desktop/mobile preview, shared existing save state. Missing-gallery test observed red; browser save/reload/preview/custom color/keyboard/320/390/403 suite passes.
- [x] Renderer: missing theme_override observed red; display.py and complete-conference.html support layout classes, appearance-presets.css implements true left-nav layout. Native menu read side effect fixed with direct read for previews; SSR12-theme tests pass.
- [x] Integration: final frontend build passed (JS642.91kB), Python services restarted. All12 saved/rendered through actual HTTP;2 layouts have distinct computed geometry. Screenshots viewed. Full editor/public/backend regressions pass. No user theme changes to22/61.
- [x] Independent review: insufficient label contrast reproduced2.59 then fixed; Chromium contrast suite covers all6 colors in2 layouts plus white/yellow custom accents; re-review ship. Documentation and README state original403/source limitation; temporary fixture cleanup and live entry verified.

Workspace is not a Git repository; source changes stay in shared workspace with explicit ownership.
