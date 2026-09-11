# ChatEyes

Screenshot-first chat compliance and moderation assistant for human moderators.

## Flow

```text
Screenshot
   ↓
Image validation
   ↓
OCR
   ↓
Chat/message reconstruction
   ↓
Language normalization
   ↓
Violation detection
   ↓
Policy decision
   ↓
MIT/Submod task plan
   ↓
Human moderation action
   ↓
Case + audit record
```

## Current API

- `GET /health` — service health.
- `POST /ocr` — extract visible text from JPEG/PNG/WebP screenshots.
- `POST /moderate` — moderate structured messages.
- `POST /tasks` — generate role-aware moderator tasks after a screenshot is available.
- `POST /analyze-screenshot` — run the current screenshot-first pipeline end to end: OCR → message reconstruction → moderation → task planning.

## Important boundary

ChatEyes currently **plans and recommends human moderation work**. It does not silently execute irreversible report, mute, or ban actions. External action integrations will require authorization, audit logging, idempotency, and a dry-run mode.

## Development

```bash
pip install -e ".[dev]"
pytest -q
uvicorn chateyes.main:app --reload
```

See [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) for the architecture, risk register, and APEA-G delivery plan.
