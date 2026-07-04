"""Extracao de texto de PDFs e chunking por sentenca."""
import re

import fitz  # PyMuPDF

from src.config import MAX_CHUNK_CHARS, CHUNK_OVERLAP_SENTENCES

# Abreviacoes comuns em documentos financeiros BR que nao terminam sentenca
_ABBREVIATIONS = r"(?<!\bSr)(?<!\bSra)(?<!\bDr)(?<!\bDra)(?<!\bart)(?<!\bInc)(?<!\bLtda)(?<!\bS\.A)(?<!\bR\$)"

_SENTENCE_SPLIT = re.compile(_ABBREVIATIONS + r"(?<=[.!?])\s+(?=[A-ZÀ-Ú0-9])")


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def chunk_sentences(sentences: list[str]) -> list[str]:
    """Agrupa sentencas em chunks de ate MAX_CHUNK_CHARS, com overlap."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for sent in sentences:
        if size + len(sent) > MAX_CHUNK_CHARS and current:
            chunks.append(" ".join(current))
            # overlap: repete as ultimas N sentencas no proximo chunk
            current = current[-CHUNK_OVERLAP_SENTENCES:]
            size = sum(len(s) for s in current)
        current.append(sent)
        size += len(sent)
    if current:
        chunks.append(" ".join(current))
    return chunks


def extract_text_chunks(pdf_path: str) -> list[dict]:
    """Retorna chunks de texto com metadados de fonte (arquivo + pagina)."""
    doc = fitz.open(pdf_path)
    results = []
    for page_num, page in enumerate(doc, start=1):
        sentences = split_sentences(page.get_text("text"))
        for chunk in chunk_sentences(sentences):
            results.append(
                {
                    "content": chunk,
                    "type": "text",
                    "source": pdf_path,
                    "page": page_num,
                }
            )
    doc.close()
    return results
