"""PDF manual discovery, extraction and indexing helpers."""

from __future__ import annotations

import hashlib
import io
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from pypdf import PdfReader


DRIVE_FOLDER_ID = os.getenv("MANUAL_DRIVE_FOLDER_ID", "1MeuXfTD9pPcjrmV-50jVc0wJJqMnZgIz")
MAX_PDF_BYTES = int(os.getenv("MAX_MANUAL_PDF_MB", "30")) * 1024 * 1024

# The current shared folder contents are kept as a safe fallback.  Cloud Run
# also tries the Drive API so newly added files appear without a code change.
DEFAULT_DRIVE_MANUALS = [
    {"id": "1YvcshZECUIc4k8OcvzrM118KyGjldIoc", "name": "EVS XTnano 테크니컬 매뉴얼.pdf"},
    {"id": "1BuaRGTv9niCYAg5FdQQVlbtStV8Vyohs", "name": "EVS XTnano 레퍼런스 매뉴얼.pdf"},
    {"id": "1z2OxZ2t16UxuivBicGyFiVxafc-kwQcy", "name": "EVS XT2 Technical Manual.pdf"},
    {"id": "1WPoAKGJwxvKiAcZ8EwBpuLunrh95Q4NY", "name": "SONY MVS3000 Manual.pdf"},
    {"id": "19druLRTdute3i3qwG5xH23k-uEBTM6VA", "name": "SONY UTX-B03, URX-P03.pdf"},
    {"id": "1t0e44t05OrON3uuB5h0vS5xChYf5foGj", "name": "SENNHEISER EM2050 Manual.pdf"},
    {"id": "1bL-5pI6YTCmq8X5ugFSf86Sl-0VH-AbP", "name": "YAMAHA DM1000_kor.pdf"},
    {"id": "1XFA9Jm0C0LXp2d3lVKlIfu3qMoHB5Tt5", "name": "YAMAHA CL 한글.pdf"},
    {"id": "1bMLB20HSMyvK1LDR5aJ6YE3999BTtk1a", "name": "DM2000 한글메뉴얼.pdf"},
]


def _drive_url(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


def list_drive_manuals() -> tuple[list[dict], str]:
    """Return PDFs in the configured folder, falling back to the verified list."""
    try:
        import google.auth
        from googleapiclient.discovery import build

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        response = service.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and trashed = false and mimeType = 'application/pdf'",
            fields="files(id,name,size,modifiedTime)",
            orderBy="name",
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = response.get("files", [])
        if files:
            return [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "size": int(item.get("size", 0)),
                    "modified_time": item.get("modifiedTime"),
                    "url": _drive_url(item["id"]),
                }
                for item in files
            ], "Google Drive 실시간 목록"
    except Exception:
        pass

    return [
        {**item, "url": _drive_url(item["id"]), "size": 0, "modified_time": None}
        for item in DEFAULT_DRIVE_MANUALS
    ], "등록된 공유 폴더 목록"


def download_drive_pdf(file_id: str) -> bytes:
    query = urllib.parse.urlencode({"id": file_id, "export": "download", "confirm": "t"})
    request = urllib.request.Request(
        f"https://drive.usercontent.google.com/download?{query}",
        headers={"User-Agent": "SPOTV-Trouble-AI/1.0"},
    )
    content = bytearray()
    # Public Drive downloads can pause for several minutes on larger manuals.
    # The timeout is per socket operation, not a total download duration.
    with urllib.request.urlopen(request, timeout=900) as response:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            content.extend(block)
            if len(content) > MAX_PDF_BYTES:
                raise ValueError(f"PDF가 {MAX_PDF_BYTES // 1024 // 1024}MB 제한을 초과합니다.")
    if not bytes(content[:5]) == b"%PDF-":
        raise ValueError("공유 파일을 PDF로 내려받지 못했습니다. Drive 공유 권한을 확인해 주세요.")
    return bytes(content)


def _split_text(text: str, target: int = 1500, overlap: int = 180) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target)
        if end < len(text):
            split_at = max(text.rfind(". ", start, end), text.rfind(" ", start, end))
            if split_at > start + target // 2:
                end = split_at + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def extract_pdf(pdf_bytes: bytes, title: str, drive_file_id: str | None = None,
                drive_url: str | None = None) -> tuple[dict, list[dict]]:
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError(f"PDF가 {MAX_PDF_BYTES // 1024 // 1024}MB 제한을 초과합니다.")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    manual_id = drive_file_id or digest[:32]
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks = []
    extracted_pages = 0
    for page_number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        page_chunks = _split_text(text)
        if page_chunks:
            extracted_pages += 1
        for index, content in enumerate(page_chunks):
            chunks.append({
                "id": f"{manual_id}-{page_number:05d}-{index:03d}",
                "manual_id": manual_id,
                "title": title,
                "page_number": page_number,
                "content": content,
                "drive_url": drive_url or "",
            })
    if not chunks:
        raise ValueError("텍스트를 추출할 수 없습니다. 이미지 스캔 PDF는 OCR 처리가 필요합니다.")
    metadata = {
        "id": manual_id,
        "title": title,
        "drive_file_id": drive_file_id or "",
        "drive_url": drive_url or "",
        "file_hash": digest,
        "page_count": len(reader.pages),
        "extracted_pages": extracted_pages,
        "chunk_count": len(chunks),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return metadata, chunks


def index_pdf_bytes(pdf_bytes: bytes, title: str, storage, drive_file_id: str | None = None,
                    drive_url: str | None = None) -> dict:
    metadata, chunks = extract_pdf(pdf_bytes, title, drive_file_id, drive_url)
    storage.replace_manual(metadata, chunks)
    return metadata
