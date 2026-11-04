"""Text extraction is not layout-preserving translation."""
import io
from pathlib import Path


def extract_text(name: str, raw: bytes) -> str:
    ext = Path(name).suffix.lower()
    if ext == ".txt":
        return raw.decode("utf-8-sig", errors="replace")
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs) + "\n" + "\n".join(
            cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    raise ValueError("TXT, PDF, DOCX 파일만 지원합니다.")
