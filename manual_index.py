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


DRIVE_FOLDER_ID = os.getenv("MANUAL_DRIVE_FOLDER_ID", "").strip()
MAX_PDF_BYTES = int(os.getenv("MAX_MANUAL_PDF_MB", "30")) * 1024 * 1024

def _drive_url(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


def list_drive_manuals() -> tuple[list[dict], str]:
    """Return PDFs in the configured Google Drive folder."""
    if not DRIVE_FOLDER_ID:
        return [], "MANUAL_DRIVE_FOLDER_ID 미설정"
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

    return [], "Google Drive 목록을 불러오지 못했습니다"


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
