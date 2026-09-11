# ChatEyes — Project Plan and Risk Register

## Product direction

ChatEyes is a screenshot-first chat compliance assistant. The core loop is:

`screen capture -> image validation -> OCR -> message reconstruction -> language normalization -> detection -> policy -> MIT/Submod task plan -> human action -> case/audit record`

The assistant should recommend moderator work, not silently take irreversible actions. Report/mute/ban integrations must be explicit, authorized, auditable, idempotent, and support dry-run mode.

## Current foundation

- FastAPI endpoints for health, OCR, structured moderation, task generation, and screenshot analysis.
- Local Tesseract OCR adapter with image-size/content-type limits.
- Unicode/zero-width normalization and heuristic script/transliteration detection.
- Four-rule moderation engine with confidence thresholds and strongest-match precedence.
- Separate role-aware moderation policy.
- MIT/Submod task planning for evidence, signature, warnings, escalation, reporting, mute requests, profile changes, and duplicate-report avoidance.
- End-to-end screenshot pipeline: OCR -> message reconstruction -> moderation -> task planning.

## Problems to prevent

| Risk | Preventive design |
|---|---|
| Raw OCR is not structured chat | Message reconstruction; preserve unmatched lines |
| OCR errors cause bad actions | Internal OCR confidence/geometry and review thresholds |
| Static regex scores are mistaken for calibrated confidence | Label current scores as rule strength; calibrate with a dataset later |
| Detector and policy drift | One policy layer between detectors and moderator tasks |
| Stateless tasks duplicate work | Persistent cases/tasks, ownership, timestamps, idempotency |
| Caller-controlled direct-report flags | Replace free-form flags with trusted typed detector findings |
| No auditability | Immutable case/task/action events with policy version |
| Image resource exhaustion | Add pixel/dimension/time/concurrency limits; verify decoded image bytes |
| English-only OCR | Multilingual OCR adapter and language-pack strategy |
| Ambiguous transliteration | Proper language ID with uncertainty/fallback |
| OCR cannot classify media | Vision/media classifier adapter; REVIEW on uncertainty |
| No privacy controls | Default no-retention processing, redaction, encrypted storage when required |
| Public endpoint abuse | Authentication, quotas, rate limits, tenant isolation |
| Production failures invisible | Correlation IDs, structured logs, metrics, tracing, alerts |
| External moderation actions unsafe | Authorization, dry-run, idempotency, receipts, retries |
| Strict public JSON becomes hard to evolve | Keep public contract stable; use richer internal evidence models |

## Delivery sequence

### A — Screenshot understanding
1. Decode/verify image bytes; add pixel and processing limits.
2. OCR adapter with multilingual configuration.
3. Message reconstruction with ordering, regions, and confidence.
4. Screenshot quality/empty-screen detection.

### B — Reliable moderation
5. Proper multilingual language identification.
6. Translation adapter with graceful fallback.
7. Detector registry for deterministic, text-ML, and media-vision detectors.
8. Calibrated confidence and review thresholds.
9. Labeled regression dataset for false-positive/false-negative evaluation.

### C — Moderator operations
10. Persistent cases and task state.
11. Task ownership, completion, cancellation, and deduplication.
12. Evidence references and screenshot hashing.
13. Policy-versioned audit trail.
14. Moderator UI/API centered on the visible chat and current task.

### D — Safe integrations
15. Report/mute/profile-change adapter interfaces.
16. Dry-run and idempotency.
17. Authorization and role permissions.
18. External action receipts and safe retry policy.

### E — Production hardening
19. Authentication and tenant isolation.
20. Rate limiting and concurrency controls.
21. Structured observability and alerting.
22. Privacy/retention/redaction controls.
23. Load, adversarial OCR, and screenshot robustness tests.
24. Deployment configuration and operational runbook.

## APEA-G operating rule

Before every feature, inspect the current architecture and identify likely future failure modes. Fix or document them before adding the next layer. CI success is necessary, not sufficient: correctness, policy, security, privacy, observability, and operational behavior all matter.
