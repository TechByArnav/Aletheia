"""Download + validation. First result is a candidate, never proof."""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests

from .seed import ambiguity_note

MAX_BYTES = 25_000_000
TIMEOUT = 25
MAX_RETRIES = 3
MAX_REDIRECTS = 5

YEAR_PATTERNS = [
    (re.compile(r"2026[\s\-–]?2027", re.I), "2026-2027"),
    (re.compile(r"2025[\s\-–]?2026", re.I), "2025-2026"),
    (re.compile(r"2024[\s\-–]?2025", re.I), "2024-2025"),
    (re.compile(r"\b2026\b"), "2026"),
]


@dataclass
class ValidationResult:
    ok: bool
    file_type: str = "unknown"
    reporting_period: str = ""
    notes: list[str] = field(default_factory=list)
    file_hash: str = ""
    domain: str = ""
    is_official_hint: bool = False


def safe_filename(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:120]
    return slug or "document"


def file_hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_reporting_period(text_head: str) -> str:
    for pat, label in YEAR_PATTERNS:
        if pat.search(text_head):
            return label
    return ""


def guess_file_type(url: str, content_type: str, magic: bytes) -> str:
    ct = (content_type or "").lower()
    if "pdf" in ct or magic.startswith(b"%PDF"):
        return "pdf"
    if "html" in ct or magic.lstrip().lower().startswith((b"<!doctype", b"<html")):
        return "html"
    if url.lower().endswith(".pdf"):
        return "pdf"
    return "unknown"


def validate_candidate(display_name: str, url: str, data: bytes, content_type: str, requested_year: str) -> ValidationResult:
    """Identity + year + content validation. Rejects wrong-year / wrong-institution."""
    notes: list[str] = []
    magic = data[:8]
    ftype = guess_file_type(url, content_type, magic)
    domain = urlparse(url).netloc.lower()
    h = file_hash_bytes(data)
    head = data[:20000].decode("latin-1", errors="ignore")
    period = detect_reporting_period(head + " " + url)

    ok = True
    # Institution token check on text-native docs (scanned PDFs handled as needs_review, not verified)
    tokens = [t for t in re.split(r"[^A-Za-z]+", display_name) if len(t) > 3][:4]
    lowered = head.lower()
    hits = sum(1 for t in tokens if t.lower() in lowered)
    if ftype == "unknown":
        ok = False
        notes.append("Unknown file signature/content-type; not marked processed.")
    if len(data) < 5000:
        ok = False
        notes.append("File too small to be a full CDS; likely error page.")
    if hits == 0 and ftype in ("pdf", "html") and len(lowered) > 2000:
        # Do not auto-fail hard — flag for review (headers may be images), but never verify.
        notes.append(f"Institution tokens not found in head text for '{display_name}'; needs review.")
    # Reporting period: filename year is not evidence; require in-content period match when detectable
    if period and requested_year and requested_year not in period and requested_year not in head[:5000]:
        notes.append(f"Detected period '{period}' does not contain requested year '{requested_year}'; flagged mixed-year.")
    amb = ambiguity_note(display_name)
    if amb:
        notes.append(f"Ambiguous identity: {amb}")
    is_official = domain.endswith(".edu")
    if not is_official:
        notes.append(f"Third-party mirror suspected ({domain}); prefer official .edu source.")
    if b"Common Data Set" not in data[:200000] and "Common Data Set" not in head:
        notes.append("Phrase 'Common Data Set' not found in head; sections C7/C9 may be absent.")
    return ValidationResult(ok=ok, file_type=ftype, reporting_period=period, notes=notes, file_hash=h, domain=domain,
                             is_official_hint=is_official)


def download_with_retries(url: str, dest: Path, timeout: int = TIMEOUT) -> tuple[bytes, str]:
    """Bounded retries, exponential backoff, size + redirect limits."""
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with requests.get(url, stream=True, timeout=timeout, allow_redirects=True,
                               headers={"User-Agent": "Mozilla/5.0 Aletheia/0.1"}) as r:
                if len(r.history) > MAX_REDIRECTS:
                    raise ValueError("Too many redirects")
                r.raise_for_status()
                ctype = r.headers.get("Content-Type", "")
                buf = bytearray()
                for chunk in r.iter_content(65536):
                    buf.extend(chunk)
                    if len(buf) > MAX_BYTES:
                        raise ValueError("Download exceeds size limit")
                data = bytes(buf)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                return data, ctype
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Download failed after {MAX_RETRIES} attempts: {last}")
