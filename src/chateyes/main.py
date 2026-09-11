from fastapi import FastAPI

from .models import ModerationResponse, TextModerationRequest
from .moderation import moderate_messages

app = FastAPI(title="ChatEyes", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/moderate", response_model=ModerationResponse)
def moderate(request: TextModerationRequest) -> ModerationResponse:
    return moderate_messages(request.messages)
