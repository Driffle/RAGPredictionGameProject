"""Temporary PDF blobs so the browser and desktop window can save a real file."""

from __future__ import annotations

import re
import time
import uuid

MAX_PDF_BYTES = 20 * 1024 * 1024
_TTL_SEC = 10 * 60
_EXPORTS: dict[str, tuple[str, bytes, float]] = {}


def safe_pdf_filename(name: str) -> str:
    raw = str(name or "").strip() or "floor-brief.pdf"
    base = raw.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")[:80]
    if not cleaned:
        cleaned = "floor-brief"
    if not cleaned.lower().endswith(".pdf"):
        cleaned += ".pdf"
    return cleaned


def _prune(now: float | None = None) -> None:
    stamp = time.time() if now is None else now
    stale = [token for token, row in _EXPORTS.items() if stamp - row[2] > _TTL_SEC]
    for token in stale:
        _EXPORTS.pop(token, None)


def store_pdf_export(filename: str, data: bytes) -> str:
    if not data or len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF is missing or too large")
    if not data.lstrip().startswith(b"%PDF"):
        raise ValueError("Not a PDF")
    _prune()
    token = uuid.uuid4().hex
    _EXPORTS[token] = (safe_pdf_filename(filename), data, time.time())
    return token


def peek_pdf_export(token: str) -> tuple[str, bytes] | None:
    _prune()
    row = _EXPORTS.get(str(token or ""))
    if not row:
        return None
    filename, data, _created = row
    return filename, data


def take_pdf_export(token: str) -> tuple[str, bytes] | None:
    _prune()
    row = _EXPORTS.pop(str(token or ""), None)
    if not row:
        return None
    filename, data, _created = row
    return filename, data
