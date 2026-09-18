# Kisan Nyay Frontend

React/Vite progressive web application for offline-first crop-loss evidence preparation and human review.

## Run locally

```bash
npm ci
npm run dev
```

With no `.env`, the application runs in an explicitly labelled **local demonstration mode**. Records and original blobs persist in IndexedDB, but the UI does not claim they reached AWS.

For AWS mode, copy `.env.example` to `.env` and fill all four stack outputs. The app then uses:

- Cognito passwordless SMS OTP
- API Gateway JWT requests
- direct presigned uploads to private S3
- upload confirmation and SQS processing
- submitted reviewer queue and correction requests
- offline retry through IndexedDB synchronization jobs

## Validate

```bash
npm run lint
npm run build
```

The application defaults to Hindi and provides an English language control. Do not commit `.env`, tokens, or captured evidence.
