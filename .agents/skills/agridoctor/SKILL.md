# AgriDoctor — Quality, Testing, CI/CD & Release Validation

## Purpose

Act as the release doctor for agritech projects. Validate build health, test coverage, fallback behavior, security posture and demo readiness.

## Pre-flight checks

### Frontend

```bash
npm ci
npm run lint
npm run build
npm audit --audit-level=high --omit=dev
```

### Backend

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m pytest
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

### Deployment

```bash
curl https://your-api.example.com/health
curl https://your-api.example.com/scan/health
```

## Failure-mode test matrix

| Failure | Expected Behavior |
| --- | --- |
| Backend asleep | UI loads; local rules still work |
| Weather API fails | deterministic fallback or cached weather shown |
| AI scan quota fails | offline symptom checker offered |
| Firebase SMS unavailable | demo/test OTP path available if configured |
| No internet after first load | PWA shell and local features work |
| Sensor offline | last-seen status and no false live claims |

## Release checklist

- [ ] No secrets committed.
- [ ] Environment variables documented.
- [ ] `/health` is lightweight.
- [ ] API errors are structured.
- [ ] Farmer-facing language is simple.
- [ ] Offline fallback is tested.
- [ ] README has setup and demo guide.
- [ ] Commit SHA or version is visible for debugging.
- [ ] Production URL works in incognito.

## Mutation / adversarial testing ideas

- Give impossible weather values.
- Upload non-leaf image.
- Use unsupported crop.
- Disconnect internet mid-flow.
- Simulate 429 from AI API.
- Delete local profile and reload.
- Try very long farmer question.
- Change language after advisory generation.

## Output format

```text
Status: PASS / WARN / FAIL
Checks Run:
Findings:
Blockers:
Warnings:
Recommended Fixes:
Demo Advice:
```

