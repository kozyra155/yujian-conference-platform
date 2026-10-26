# Conference account implementation plan

**Goal:** Visitors can find conference registration/login, verify email, create a native account, and return to actual registration/submission.

**Architecture:** Native authentication and email token lifecycle, small plugin context/link helper, existing branded auth templates and shared portal script. No new dependency or identity store. User authorized email verification; implementation proceeds within that scope.

- [x] Add failing real integration check `verify_conference_accounts.py`: contextual links, actual CAPTCHA/locmem verification email, new-browser token, native signup, returned business target and real native submissions; security/cleanup checks.
- [x] Add `worker/extension/yujian_site/conference_accounts.py`: safe same-event targets, context, native email-link continuation. Integrate plugin hook/blueprint GET aliases and public conference action/header links, preserving native checks.
- [x] Add contextual auth card partial and scoped CSS; wire login/register views and reverse links. Preserve native forms. Fix portal login URL reset/guest signup visibility. Browser failing check then responsive/language/link preservation check.
- [x] Build/restart after coherent source; run fresh tests, native/global auth and LAN regressions. Independent review as required by requesting-code-review skill, fix findings, document evidence and clean temporary data.

No Git repository. Do not read/print secrets, send external messages, change SMTP credentials, mutate meetings22/61, or bypass email verification.

Completed: real CAPTCHA and locmem email verification, fresh-browser native signup, email login, return to native registration/submission, security boundaries, responsive/bilingual UI and SMTP authentication checks passed. Independent read-only review found no important issues. No changes to meetings22/61. Temporary account/conference records checked at zero active. Evidence: ../../conference-account-validation.md.
