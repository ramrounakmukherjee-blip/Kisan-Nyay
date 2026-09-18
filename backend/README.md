# Kisan Nyay AWS Backend

Serverless backend deployed with AWS SAM. See [`../docs/AWS_ARCHITECTURE.md`](../docs/AWS_ARCHITECTURE.md) and [`../docs/AWS_DEPLOYMENT.md`](../docs/AWS_DEPLOYMENT.md).

## Validate

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt aws-sam-cli
.venv/bin/pytest -q
.venv/bin/sam validate --lint
.venv/bin/sam build
```

The validated stack builds three Python 3.11 functions: API, SQS evidence processor, and Cognito post-confirmation farmer-role assignment.

The public health route is `GET /health`. Every evidence or review route requires a Cognito JWT when deployed. Local API events must include representative JWT claims; the API no longer falls back to a test user when identity claims are absent.
