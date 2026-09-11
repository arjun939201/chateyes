from io import BytesIO

from PIL import Image
import pytest

from chateyes.ocr import OCRProcessingError, TesseractOCR


def _png_bytes(size: tuple[int, int]) -> bytes:
    image = Image.new("RGB", size, "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_ocr_rejects_oversized_pixel_count() -> None:
    with pytest.raises(OCRProcessingError, match="dimensions exceed"):
        TesseractOCR().extract_text(_png_bytes((5000, 5000)))


def test_ocr_rejects_non_image_payload() -> None:
    with pytest.raises(OCRProcessingError):
        TesseractOCR().extract_text(b"not an image")
