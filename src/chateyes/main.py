from fastapi import FastAPI, File, HTTPException, UploadFile, status

from .models import OCRResponse, ModerationResponse, TextModerationRequest
from .moderation import moderate_messages
from .ocr import OCRConfigurationError, OCRProcessingError, TesseractOCR
from .pipeline import ScreenshotAnalysisResponse, analyze_screenshot
from .tasks import Role, TaskGenerationRequest, TaskPlanResponse, generate_tasks

app = FastAPI(title="ChatEyes", version="0.3.0")

_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ocr")
def ocr_health() -> dict[str, object]:
    """Report whether the Tesseract executable is available to the service."""
    runtime = TesseractOCR.runtime_status()
    return {
        "status": "ok" if runtime.available else "unavailable",
        "engine": TesseractOCR.engine_name,
        "executable": runtime.executable,
        "version": runtime.version,
    }


@app.post("/moderate", response_model=ModerationResponse)
def moderate(request: TextModerationRequest) -> ModerationResponse:
    return moderate_messages(request.messages)


@app.post("/tasks", response_model=TaskPlanResponse)
def tasks(request: TaskGenerationRequest) -> TaskPlanResponse:
    """Generate human-moderator tasks once a captured screen is available."""
    moderation = moderate_messages(request.messages)
    plan = generate_tasks(
        moderation,
        role=request.role,
        screenshot_available=request.screenshot_available,
        moderator_present=request.moderator_present,
        signature_detected=request.signature_detected,
        warning_count=request.warning_count,
        user_stopped=request.user_stopped,
        direct_report_flags=set(request.direct_report_flags),
    )
    return TaskPlanResponse(
        screenshot_ready=request.screenshot_available,
        total_tasks=len(plan),
        tasks=plan,
    )


@app.post("/analyze-screenshot", response_model=ScreenshotAnalysisResponse)
async def analyze_captured_screenshot(
    file: UploadFile = File(...),
    role: Role = "MIT",
    warning_count: int = 0,
) -> ScreenshotAnalysisResponse:
    """Capture -> OCR -> chat parsing -> moderation -> MIT task planning."""
    image_bytes = await file.read(_MAX_IMAGE_BYTES + 1)
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are supported.",
        )
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds the 10 MB size limit.",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file is empty.",
        )
    if warning_count < 0:
        raise HTTPException(status_code=422, detail="warning_count cannot be negative")

    try:
        return analyze_screenshot(image_bytes, role=role, warning_count=warning_count)
    except OCRConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except OCRProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@app.post("/ocr", response_model=OCRResponse)
async def ocr_screenshot(file: UploadFile = File(...)) -> OCRResponse:
    """Extract visible text from a supported chat screenshot."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are supported.",
        )

    image_bytes = await file.read(_MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds the 10 MB size limit.",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file is empty.",
        )

    try:
        result = TesseractOCR().extract_text(image_bytes)
    except OCRConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except OCRProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return OCRResponse(text=result.text, engine=result.engine, language=result.language)
