# Company payments implementation plan

**Goal:** Complete company-owned conference collection, payment verification, refunds, invoice requests and exports without changing existing meetings.

**Architecture:** Native registration prices and transactions; one durable EventSetting order per registration; company-only collection configuration; signed optional gateways; existing Vue/Element Plus workspace.

**Tech Stack:** Flask/Indico, PostgreSQL row/advisory locks, cryptography/requests already installed, Vue 3/Element Plus, Playwright.

- [x] Add `tests/backend/verify_payments.py` with a temporary company administrator, organizer, two attendees, CNY fee form, locmem mail. First assert company config endpoint exists, run and observe 404.
- [x] Implement `payments.py`: strict Decimal amount validation, company settings, row-locked immutable order, audit, native successful/cancel transactions, bank reference uniqueness, full-refund and invoice applications, private serialization and CSV safety.
- [x] Implement `payment_routes.py`: administrator configuration; full-manager fee setup/order view/export; owner payment/detail/receipt/application; administrator financial decisions. Register from blueprint; reuse RHAccount, RHManaged, CSRF and event locking.
- [x] Implement `payment_gateways.py`: RSA2 Alipay page URL/verified notifications, WeChat Native signed HTTP/verified encrypted notifications, fixed hosts, timeouts, merchant/amount checks. No real gateway calls in verification.
- [x] Wire native unpaid checkout, registration-created/approved signals, participant payment links and company finance sidebar. Block native paid toggles for company events so organizer cannot bypass finance verification.
- [x] Build `PaymentWorkspace.vue` and integrate App.vue mode/navigation and BusinessWorkspace links. Keep responsive branded layouts, server error handling, confirmation dialogs, CNY amounts and bilingual labels.
- [x] Verify real native fee registration → pending approval → unpaid → transfer review → administrator receipt → complete → invoice request/issue → refund request/confirm → withdrawn; assert permissions, CSRF, amount mismatch, duplicate reference and idempotency. Add signed fake callback tests and amount/merchant/signature rejection.
- [x] Build frontend, restart web/celery, run Playwright payment screens at 320/390/1440 and independent code review. Run existing account/business and LAN regressions. Document setup and limitations, remove active fixtures.

Commands: `Get-Content tests/backend/verify_payments.py -Raw | docker compose -p yujian-indico-v1 exec -T indico-web /opt/indico/.venv/bin/python -`; `npm run build` in frontend; `node tests/browser/verify_payments_ui.cjs`; existing `tests/backend/verify_business_lifecycle.py`, `tests/backend/verify_conference_accounts.py`, `tests/browser/verify_lan_access.cjs`.

Completed: company configuration remains empty/disabled, online gateways remain disabled on LAN HTTP. Existing meetings22/61 unchanged. Review fixes: normalize native float totals, preserve financial records on deletion/purge, reject conflicting refund retries, refresh locked orders for concurrent callbacks, lock first-order form/event eligibility, require nonempty consent even for zero-base paid-option forms. No real money moved or outside test email sent.
