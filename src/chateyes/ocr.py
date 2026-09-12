from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import shutil
import subprocess

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


@dataclass(frozen=True)
class OCRRuntimeStatus:
    available: bool
    executable: str | None
    version: str | None


class TesseractOCR:
    """Local OCR adapter around Tesseract, kept behind a small replaceable interface."""

    engine_name = "tesseract"
    allowed_formats = frozenset({"JPEG", "PNG", "WEBP"})
    max_pixels = 20_000_000

    def __init__(self, language: str = "eng") -> None:
        self.language = language

    @classmethod
    def runtime_status(cls) -> OCRRuntimeStatus:
        executable = shutil.which("tesseract")
        if not executable:
            return OCRRuntimeStatus(False, None, None)
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            first_line = (result.stdout or result.stderr).splitlines()[0].strip()
            return OCRRuntimeStatus(result.returncode == 0, executable, first_line or None)
        except (OSError, subprocess.SubprocessError):
            return OCRRuntimeStatus(False, executable, None)

    def extract_text(self, image_bytes: bytes) -> OCRResult:
        try:
            import pytesseract
        except ImportError as exc:
            raise OCRConfigurationError(
                "Tesseract OCR Python dependencies are not installed."
            ) from exc

        runtime = self.runtime_status()
        if not runtime.available:
            raise OCRConfigurationError(
                "Tesseract OCR engine is unavailable in the deployment environment."
            )

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
        except OCRConfigurationError:
            raise
        except OCRProcessingError:
            raise
        except Exception as exc:
            raise OCRProcessingError(
                "OCR failed while processing the image. Verify the image and OCR language data."
            ) from exc

        return OCRResult(
            text=_clean_text(text),
            engine=self.engine_name,
            language=self.language,
        )

    @staticmethod
    def _prepare(image: Image.Image) -> Image.Image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        width, height = image.size
        if width < 1600:
            scale = min(1600 / max(width, 1), 3.0)
            image = image.resize((int(width * scale), int(height * scale)))
        return ImageOps.grayscale(image)


def _clean_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()
