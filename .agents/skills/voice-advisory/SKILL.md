# Voice Advisory — Vernacular Farmer Assistance

## Purpose

Create multilingual, voice-first, farmer-friendly advisory experiences for rural users.

## Target languages

Starter language set:

- English
- Hindi
- Bengali
- Marathi

Extend with regional language packs as needed.

## Advisory writing rules

Farmer-facing messages should be:

- short,
- specific,
- action-oriented,
- non-alarming,
- explainable,
- safe,
- available in local language.

## Message template

```text
Alert: What is happening?
Why: Why is this risk high?
Action: What should the farmer do today?
Avoid: What should the farmer not do?
Follow-up: When to check again or call expert?
```

## Voice interaction model

```mermaid
flowchart LR
    Farmer[Farmer Speech/Text] --> ASR[Speech Recognition]
    ASR --> Intent[Intent Classifier]
    Intent --> Data[Local Farm Data]
    Data --> Response[Simple Advisory]
    Response --> TTS[Read Aloud]
```

## Intent categories

- weather summary,
- pest risk,
- disease risk,
- irrigation timing,
- market price,
- crop stage,
- scan result explanation,
- emergency warning,
- fallback/help.

## Sample tone

Instead of:

```text
Your field has an 82% sheath blight probability due to epidemiological parameters.
```

Say:

```text
There is a high chance of sheath blight because the crop is in a sensitive stage and humidity is high after rain. Check the lower leaves today and avoid extra watering.
```

## Offline design

- Prefer rule-based local answers for critical guidance.
- Use device speech APIs where possible.
- Cache translations.
- Avoid cloud-only voice dependency.
- Provide tap chips for users who cannot or do not want to type.

