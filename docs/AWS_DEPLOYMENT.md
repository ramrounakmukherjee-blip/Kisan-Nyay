# AWS Deployment

## Prerequisites

- An AWS account and CLI credentials for the hackathon account
- AWS SAM CLI
- Python 3.11
- Node.js 20 or newer and npm
- Permission to create CloudFormation, IAM, Cognito, API Gateway, Lambda, DynamoDB, S3, SQS, CloudWatch, and X-Ray resources
- Cognito/SNS SMS access appropriate for the destination numbers. New accounts can have SMS sandbox and spend-limit restrictions; Indian delivery can require registered origination configuration.

## Validation completed in this repository

From `backend/`, the following pass:

```bash
pytest -q                    # 5 API security/lifecycle tests
sam validate --lint         # valid SAM template
sam build                   # all three Python 3.11 functions build
```

From `frontend/`, both commands pass:

```bash
npm run lint
npm run build
```

## Automated deployment with GitHub OIDC

`.github/workflows/deploy-aws.yml` performs the remaining deployment without storing long-lived AWS access keys. One-time account authorization is still required:

1. Configure GitHub as an IAM OIDC identity provider in the hackathon AWS account.
2. Create a least-privilege deployment role whose trust policy permits this repository and the protected GitHub environment (`dev`, `staging`, or `prod`).
3. Create the Amplify Hosting app and connect its branch using `amplify.yml`.
4. Add these **repository or environment variables**, not secrets copied into source:
   - `AWS_DEPLOY_ROLE_ARN` — ARN of the OIDC deployment role
   - `AMPLIFY_APP_ID` — target Amplify app ID
   - `AMPLIFY_BRANCH` — connected branch name
5. In GitHub Actions, run **Deploy Kisan Nyay to AWS**, select the environment, and enter the exact Amplify HTTPS origin.

The workflow obtains short-lived credentials, validates/builds SAM, deploys CloudFormation, reads stack outputs, updates all four Amplify `VITE_*` variables, and starts an Amplify release. GitHub environment approval rules should protect staging and production.

## 1. Deploy the backend manually

Use the real Amplify origin for `AllowedOrigin`; do not leave a production stack configured for localhost.

```bash
cd backend
cp samconfig.toml.example samconfig.toml
sam validate --lint
sam build
sam deploy --guided
```

Recommended guided values:

- Stack: `kisan-nyay-dev`
- Region: `ap-south-1`
- Parameter `Environment`: `dev`
- Parameter `AllowedOrigin`: the exact HTTPS Amplify hostname
- Allow SAM to create IAM roles: yes
- Save arguments to `samconfig.toml`: yes

Retrieve outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name kisan-nyay-dev \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table
```

## 2. Provision an authorized reviewer

Farmer users self-register and are assigned to `Farmers` by the post-confirmation trigger. Reviewer users must be provisioned by an administrator. Passwordless reviewer users require a verified phone number in E.164 format.

```bash
POOL_ID="<UserPoolId stack output>"
REVIEWER_PHONE="+91XXXXXXXXXX"

aws cognito-idp admin-create-user \
  --user-pool-id "$POOL_ID" \
  --username "$REVIEWER_PHONE" \
  --user-attributes Name=phone_number,Value="$REVIEWER_PHONE" Name=phone_number_verified,Value=true \
  --message-action SUPPRESS

aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$POOL_ID" \
  --username "$REVIEWER_PHONE" \
  --group-name Reviewers
```

Do not add public self-registration for reviewer access.

## 3. Configure the frontend

Create `frontend/.env` from the stack outputs:

```dotenv
VITE_AWS_API_URL=<ApiUrl>
VITE_AWS_REGION=ap-south-1
VITE_COGNITO_USER_POOL_ID=<UserPoolId>
VITE_COGNITO_CLIENT_ID=<UserPoolClientId>
```

Never commit `.env`.

## 4. Deploy with Amplify Hosting

The repository root contains `amplify.yml` with `frontend` as the application root.

1. Connect this repository and branch in Amplify Hosting.
2. Configure the four `VITE_*` variables above in Amplify environment variables.
3. Deploy the frontend.
4. If the generated Amplify hostname differs from `AllowedOrigin`, redeploy the backend with the exact hostname and rebuild the frontend.

## 5. Smoke tests

```bash
curl "$API_URL/health"
aws cloudformation describe-stacks --stack-name kisan-nyay-dev
aws dynamodb describe-table --table-name kisan-nyay-dev
aws sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names All
```

Browser checks:

1. Farmer OTP sign-up succeeds and the ID token contains `Farmers`.
2. A case and original photograph remain usable while offline.
3. Returning online changes the local state through creating, uploading, submitting, then AWS synchronized.
4. The S3 object remains private and carries `sha256` and `case-id` metadata.
5. The DynamoDB evidence record reaches `PROCESSING_QUEUED`, then `PROCESSED`.
6. A reviewer sees the submitted case and can open a five-minute evidence link.
7. A reviewer correction request appears in the farmer case list after synchronization.
8. Supplying a correction uploads a new original and appends audit records.

## Operational checklist

- Set an AWS Budget and billing alerts before the public demo.
- Move Cognito SMS out of sandbox and configure India-compliant origination if required.
- Use separate `dev`, `staging`, and `prod` stacks.
- Define retention/deletion policy and farmer consent operations before production use.
- Add WAF/rate controls if exposed beyond a hackathon pilot.
- Perform accessibility, slow-network, storage-quota, and offline-recovery tests on physical mobile devices.
