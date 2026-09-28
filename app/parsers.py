from pathlib import Path
from docx import Document
from pypdf import PdfReader
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext == ".docx":
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ext == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == ".epub":
        book = epub.read_epub(str(path))
        parts = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            parts.append(soup.get_text("\n"))
        return "\n".join(parts)
    raise ValueError(f"Unsupported file type: {ext}")
