# Kisan Nyay AWS Ship It Architecture

## Goal

Deploy the offline-first farmer workflow as a secure serverless system in `ap-south-1`, while preserving an explicitly labelled local demonstration when AWS is unavailable.

## Implemented infrastructure

- **AWS SAM** (an AWS open-source project) for reproducible infrastructure
- **API Gateway HTTP API** with a Cognito JWT authorizer
- **Amazon Cognito Essentials** passwordless SMS OTP and Farmer/Reviewer groups
- A post-confirmation Lambda that assigns self-registered users to `Farmers`; reviewer accounts remain administrator-provisioned
- **AWS Lambda Powertools** for structured logs, traces, and custom metrics
- **DynamoDB** single-table storage with point-in-time recovery, TTL for idempotency records, a farmer index, and a submitted-review index
- Private, encrypted, versioned **Amazon S3** evidence storage
- Ten-minute, browser-to-S3 presigned PUT URLs and five-minute reviewer GET URLs
- **Amazon SQS**, server-side encryption, a dead-letter queue, and partial-batch failure handling
- A Lambda receipt processor that marks durable evidence receipt without pretending to run AI analysis
- CloudWatch and X-Ray through active tracing and Powertools
- Amplify Hosting build configuration for the React PWA

## Evidence and synchronization flow

1. The PWA stores a draft, original media blobs, capture metadata, and SHA-256 fingerprints in IndexedDB.
2. A finalized local record creates an IndexedDB synchronization job.
3. After Cognito authentication and when online, the PWA creates a cloud case using an idempotency key.
4. The API ownership-checks the case and records an idempotent evidence identifier in DynamoDB.
5. The API returns a short-lived S3 PUT URL scoped to the farmer, case, evidence kind, MIME type, SHA-256 metadata, and S3 native `ChecksumSHA256` header. S3 rejects bytes that do not match the signed checksum.
6. The browser uploads the original blob directly to private S3.
7. The browser calls the evidence-completion endpoint. Lambda uses `HeadObject` to confirm size and metadata before enqueueing SQS.
8. The SQS processor marks the evidence record `PROCESSED`. No unsupported evidence score or automated claim decision is produced.
9. Once every upload is confirmed, the case enters the DynamoDB `STATUS#SUBMITTED` reviewer index.
10. An authorized reviewer retrieves documentary metadata and short-lived evidence links, then may append a correction request.
11. Farmer sync pulls open requests into IndexedDB. The supplied original file is uploaded through the same lifecycle and the append-only correction event is recorded.

## API routes

| Method | Route | Access |
| --- | --- | --- |
| `GET` | `/health` | Public health status only |
| `POST` | `/cases` | Authenticated farmer |
| `GET` | `/cases` | Farmer-owned list or reviewer submitted queue |
| `GET` | `/cases/{caseId}` | Owner or `Reviewers` group |
| `POST` | `/cases/{caseId}/evidence-url` | Case owner |
| `POST` | `/cases/{caseId}/evidence/{evidenceId}/complete` | Case owner |
| `POST` | `/cases/{caseId}/submit` | Case owner |
| `POST` | `/cases/{caseId}/requests` | `Reviewers` group |
| `POST` | `/cases/{caseId}/requests/{requestId}/complete` | Case owner |

## Security boundaries

- S3 Block Public Access and bucket-owner-enforced object ownership are enabled.
- Cognito protects every route except `/health`.
- Farmer reads, uploads, confirmations, submissions, and correction completion are ownership checked.
- Reviewer actions require the `Reviewers` Cognito group claim.
- Reviewer accounts cannot be self-registered through the public reviewer entry.
- DynamoDB, S3, and SQS encryption are enabled.
- No phone numbers, coordinates, images, documents, JWTs, or presigned URLs should be logged.
- File size, MIME type, SHA-256 format, S3 native SHA-256 checksum, object size, and object metadata are validated.
- Presigned evidence upload URLs expire after ten minutes; reviewer links expire after five minutes.
- Original S3 objects are private and versioned. Corrections append records rather than replacing originals.

## Honest scope

The repository contains deployable infrastructure and cloud-integrated frontend code, but AWS features are live only after deploying the SAM stack and configuring the frontend environment. Local mode is labelled as a demonstration and never claims cloud synchronization.

Textract, Bedrock, Step Functions, EventBridge, SNS notifications, weather feeds, government claim submission, and insurer integrations are not implemented. Cognito uses SNS only to deliver configured authentication OTPs; account SMS sandbox and India origination requirements must be satisfied in the deployment account.
