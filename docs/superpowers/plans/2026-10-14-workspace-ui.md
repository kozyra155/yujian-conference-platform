# Unified workspace UI implementation plan

**Goal:** Modernize the requested Indico entry points and the conference display without changing access control or destroying organizer content.

**Architecture:** Keep Indico request validation and database operations. Serve a locally built Vue/Element Plus workbench through plugin templates; render conference pages after native access checks. Restyle remaining native editor/account screens.

**Tech stack:** Vue 3.5.44, Element Plus 2.14.7, Vite 8.3.4, Indico 3.3.13.

- [x] Add a failing browser check for native entry points, dashboard, public site structure.
- [x] Build the local component bundle and workbench views; wire native category/dashboard entry points.
- [x] Implement the conference display template using visible native menu entries and sanitized content.
- [x] Unify native content editor/account appearance, preserving native forms.
- [x] Run backend access regression and actual browser creation/edit/publication/language checks.
- [x] Inspect desktop/mobile screenshots, fix layout defects, document build instructions and limitations.
