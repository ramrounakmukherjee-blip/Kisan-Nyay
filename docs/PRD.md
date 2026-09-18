# Kisan Nyay — MVP Product Requirements

## Product statement
A Hindi/English, offline-first crop-loss evidence assistant that helps Indian farmers create a structured record for insurance or extension-worker assistance. It does not guarantee eligibility, compensation, or official submission.

## MVP users
- Farmer: registers loss, captures evidence, saves offline, and tracks progress.
- Extension worker/FPO representative: reviews evidence and requests corrections (phase 2).

## Core farmer journey
1. Select a registered field and loss event.
2. Capture guided wide and close-up photographs with location metadata.
3. estimate affected area and select crop stage.
4. Review, declare accuracy, and save the evidence record locally.
5. Synchronize when connectivity returns (phase 2 backend).

## Scope
- Hindi and English
- All-India adaptable data model
- Demonstration scenario: paddy loss from flooding or unseasonal rain
- Mobile-first PWA interface
- Honest “assistance record” terminology

## Current prototype
The frontend in `frontend/` implements the primary farmer flow, language switching, responsive design, simulated offline status, evidence checklist, damage assessment, and confirmation state.

## Next milestones
1. IndexedDB persistence and installable service worker
2. Camera/GPS browser integrations
3. FastAPI API, PostgreSQL schema, and object storage
4. Extension-worker dashboard and status audit log
5. Server-side evidence PDF generation
6. State/scheme configuration system

## Safety and privacy
- Obtain consent before location/photo capture.
- Encrypt transport and restrict case access by role.
- Never represent machine estimates as legal verification.
- Clearly distinguish local save, assisted review, and official submission.
- Provide deletion and correction paths.

## Success measures
- Completion rate of evidence records
- Percentage of records passing the evidence checklist
- Time needed to create a complete report
- Offline save and later-sync success rate
- Number of correction cycles before reviewer acceptance
