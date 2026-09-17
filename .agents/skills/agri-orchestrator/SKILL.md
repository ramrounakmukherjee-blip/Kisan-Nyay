# Agri Orchestrator — Master Router & Intent Classifier

## Purpose

Route every agritech request to the right specialist skill, preserve project context, prevent scope drift, and convert broad product goals into executable technical plans.

## When to use

Use this skill when the user asks to:

- start a new agritech project,
- add a major module,
- prepare for SIH or finals,
- split work across multiple agents,
- decide whether a feature is software, hardware, AI, IoT or roadmap,
- reconcile conflicting requirements.

## Core capabilities

- Intent classification
- Agent routing
- Requirement normalization
- Risk identification
- Demo-path planning
- Built-now vs future-roadmap separation
- Acceptance criteria creation

## Routing map

| User intent | Route to |
| --- | --- |
| PRD, judging questions, pitch | `agri-design` |
| Backend, schema, API, sync | `agri-architect` |
| Parallel implementation | `swarm-coding` |
| Leaf image AI, TFLite, model pipeline | `crop-vision` |
| Sensor/MQTT/edge telemetry | `telemetry-stream` |
| Languages, TTS, voice bot | `voice-advisory` |
| Testing, linting, CI, release | `agridoctor` |

## Standard orchestration flow

```mermaid
flowchart LR
    A[User Request] --> B[Classify Intent]
    B --> C[Extract Constraints]
    C --> D[Choose Skills]
    D --> E[Create Task Packets]
    E --> F[Parallel Execution]
    F --> G[Integration Review]
    G --> H[Demo/Deploy Checklist]
```

## Task packet format

```text
Task ID:
Assigned Skill:
Goal:
Inputs:
Files/Modules:
Constraints:
Definition of Done:
Validation:
```

## Guardrails

- If a feature depends on paid AI APIs, require a fallback.
- If a feature claims official government use, mark it as roadmap unless actually built.
- If the project is hardware, do not leak software-only secret modules into the hardware deck.
- If the user asks for a demo, optimize reliability over novelty.
- If unclear, choose the smallest useful scope and state assumptions.

