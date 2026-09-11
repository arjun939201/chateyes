from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps


class OCRConfigurationError(RuntimeError):
    """Raised when the configured OCR engine is unavailable."""


class OCRProcessingError(RuntimeError):
    """Raised when an image cannot be processed by the OCR engine."""


@dataclass(frozen=True)
class OCRResult:
    text: str
    engine: str
    language: str


class TesseractOCR:
    """Local OCR adapter around Tesseract, kept behind a small replaceable interface."""

    engine_name = "tesseract"
    allowed_formats = frozenset({"JPEG", "PNG", "WEBP"})
    max_pixels = 20_000_000

    def __init__(self, language: str = "eng") -> None:
        self.language = language

    def extract_text(self, image_bytes: bytes) -> OCRResult:
        try:
            import pytesseract
        except ImportError as exc:
            raise OCRConfigurationError(
                "Tesseract OCR dependencies are not installed."
            ) from exc

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                if image.format not in self.allowed_formats:
                    raise OCRProcessingError("Image format is not supported by the OCR pipeline.")
                width, height = image.size
                if width * height > self.max_pixels:
                    raise OCRProcessingError("Image dimensions exceed the OCR processing limit.")
                image.load()
                prepared = self._prepare(image)
                text = pytesseract.image_to_string(prepared, lang=self.language)
        except OCRProcessingError:
            raise
        except Exception as exc:  # OCR libraries expose several engine-specific errors.
            raise OCRProcessingError("Unable to extract text from the image.") from exc

        return OCRResult(
            text=_clean_text(text),
            engine=self.engine_name,
            language=self.language,
        )

    @staticmethod
    def _prepare(image: Image.Image) -> Image.Image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        # Upscaling improves small chat-font recognition without changing the source file.
        width, height = image.size
        if width < 1600:
            scale = min(1600 / max(width, 1), 3.0)
            image = image.resize((int(width * scale), int(height * scale)))
        return ImageOps.grayscale(image)


def _clean_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()
