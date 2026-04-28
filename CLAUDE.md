# N1 Payments Website Instructions

## Project Type
- This repository is a static marketing site.
- Main technologies: plain HTML, shared CSS, image assets, and a small amount of JS.
- There is no framework, build step, or app server unless explicitly added later.

## Core Working Rules
- Always pull the latest `main` before making changes.
- Make only the change the user asked for.
- Preserve the current layout, spacing, branding, and page structure unless the user explicitly asks for a redesign.
- Prefer small, targeted edits over large rewrites.
- Do not refactor unrelated sections.
- Do not reformat unrelated files just because you touched them.

## Things You Must Not Change Unless Explicitly Asked
- Deployment configuration
- Domains
- Forms or form endpoints
- Analytics or tracking scripts
- Secrets, tokens, or environment settings
- GitHub settings
- Sitewide navigation structure beyond the requested task
- File names, routes, or folder structure unless the task requires it

## Git Workflow
- Before editing, run:

```bash
git pull origin main
```

- After edits:
  - preview locally
  - summarize which files changed
  - commit with a short clear message
  - push to `main` only if the user asked for the change to be shipped

## Local Preview
- Use this command from the repo root:

```bash
python3 -m http.server 4173
```

- Then preview in browser at:

```text
http://localhost:4173/
```

## Required Checks Before Commit Or Push
- The requested page loads
- No broken internal links on the changed area
- No missing images
- Desktop layout still looks correct
- Mobile layout still looks correct if the change affects layout, spacing, navigation, or hero sections
- No unrelated files were changed without reason

## Key Paths
- Homepage: `index.html`
- Core pages:
  - `about.html`
  - `card-payments.html`
  - `online-payments.html`
  - `business-funding.html`
  - `contact.html`
- Industry pages:
  - `industries/trade/index.html`
  - `industries/hospitality/index.html`
  - `industries/retail/index.html`
  - `industries/beauty/index.html`
- Shared styles:
  - `assets/header-shared.css`
  - `assets/alternate-shared.css`
- Images:
  - `assets/photos/`

## Content And Design Guidance
- This is a customer-facing marketing site. Copy must read naturally and stay commercially credible.
- Keep wording direct and practical. Avoid generic AI-sounding phrasing.
- If updating images, use appropriately sized assets and avoid oversized originals when optimized formats are more suitable.
- When changing hero sections, verify crop, aspect ratio, and first-viewport balance.
- If a request is ambiguous, prefer preserving the current live look and changing the minimum necessary.

## If Something Looks Risky
- Stop before making a broad or destructive change.
- Explain what looks risky.
- Suggest the smallest safe option first.
