# Kisan Nyay AWS Ship It Demo Script

## Before recording

- Deploy the SAM stack and Amplify frontend using `docs/AWS_DEPLOYMENT.md`.
- Confirm the farmer and reviewer phones can receive Cognito OTP messages.
- Confirm the reviewer belongs to the `Reviewers` Cognito group.
- Use a consented, non-sensitive sample photograph and clearly identify the Sitapur paddy scenario as demonstration data.

## Farmer and offline workflow

1. Open the public landing page; do not begin on a dashboard.
2. Explain the boundary: Kisan Nyay prepares a crop-loss evidence dossier and human review record. It does not certify loss, decide eligibility, submit an official claim, or guarantee compensation.
3. Choose Hindi farmer access and authenticate with a real Cognito SMS OTP.
4. Enter the farmer and field profile. Explain that these values are farmer-entered rather than externally verified.
5. Disconnect the network and begin a flood/waterlogging record.
6. Capture a whole-field image, close-up image, device GPS (with permission), and optional voice statement.
7. Show that permission denial is displayed as unavailable; Kisan Nyay does not substitute fabricated coordinates.
8. Show the SHA-256-backed capture checklist, farmer damage-range estimate disclosure, and unchecked declaration.
9. Confirm the declaration and save. Show the truthful `Stored on device` state.

## AWS synchronization

10. Restore the network and select **Sync now**.
11. Show explicit creating, uploading, submitting, and synchronized states.
12. In AWS, show the private/versioned S3 object, its `sha256` and `case-id` metadata, the DynamoDB append-only records, and the SQS evidence receipt reaching `PROCESSED`.
13. Emphasize that this processor confirms durable receipt only; Textract, Bedrock, and automated assessment are not active.

## Connected reviewer workflow

14. Sign out and enter through **Reviewer access** with an administrator-provisioned reviewer.
15. Show the Cognito-authenticated submitted queue rather than sample metrics or a fabricated map.
16. Open the documentary case: farmer-entered fields, S3 evidence links, MIME/size, SHA-256 metadata, and audit events.
17. Request one specific additional boundary photograph. Explain that this is a human follow-up, not a claim decision.
18. Return to farmer access, synchronize, and show the correction request in the local case list.
19. Capture the requested original photograph. Show it synchronize through the same presigned upload, S3 confirmation, SQS, and append-only correction lifecycle.
20. Switch to English and print/download the bilingual dossier.

## Offline fallback disclosure

If AWS credentials, SMS, or the deployed stack are unavailable during judging, use local mode only and state clearly that its reviewer records are labelled sample data and no AWS synchronization is occurring. Do not present local demonstration behavior as a deployed integration.
