# Conference menu editor plan

**Goal:** Replace the remaining native menu editing layout with a branded organizer workbench while retaining its native business operations.

**Architecture:** After native access checks, use a WPMenuEdit subclass to render a plugin template that inherits the existing content block and scripts. Add an Element Plus toolbar and a DOM presentation layer; retain native forms, rich text, AJAX endpoints and sortable behavior.

- [x] Add a failing check for the redesigned editor at conference 22.
- [x] Implement the scoped plugin view/template and Element Plus editor toolbar.
- [x] Style and enhance native list rows and rich text dialog; preserve locked and custom-menu-disabled states.
- [x] Apply the shared shell to self profile/account pages and the legacy participation dashboard as requested.
- [x] Verify real operations using a disposable conference, permissions, language and responsive layouts.
- [x] Inspect screenshots, request independent review, document results.
