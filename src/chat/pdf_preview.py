"""Grounding visual: renderiza a pagina do PDF com o trecho citado destacado.

"Nao confie, verifique": ao abrir uma fonte na UI, o usuario ve a pagina real
do documento com o conteudo do chunk marcado em amarelo. Para chunks de tabela
e de grafico (cujo conteudo indexado nao e texto literal da pagina), a pagina
e renderizada sem destaque — ainda assim o usuario confere com os olhos.
"""
import re

import fitz

from src.config import SAMPLE_DOCS_DIR

_PREVIEW_DPI = 110
_MAX_PHRRASES = 8
_WORDS_PER_PHRASE = 6


def _search_phrases(chunk_content: str) -> list[str]:
    """Frases curtas do chunk para localizar na pagina via search_for."""
    text = re.sub(r"\s+", " ", chunk_content).strip()
    words = text.split(" ")
    phrases = []
    for i in range(0, len(words), _WORDS_PER_PHRASE + 2):
        phrase = " ".join(words[i : i + _WORDS_PER_PHRASE])
        # pula pedacos de markdown de tabela e fragmentos curtos demais
        if len(phrase) < 15 or "|" in phrase or "---" in phrase:
            continue
        phrases.append(phrase)
        if len(phrases) >= _MAX_PHRRASES:
            break
    return phrases


def render_source_page(source_name: str, page_number: int, chunk_content: str) -> bytes | None:
    """PNG da pagina citada, com o conteudo do chunk destacado quando possivel."""
    pdf_path = SAMPLE_DOCS_DIR / source_name
    if not pdf_path.exists():
        return None
    try:
        doc = fitz.open(pdf_path)
        if not 1 <= page_number <= len(doc):
            doc.close()
            return None
        page = doc[page_number - 1]
        for phrase in _search_phrases(chunk_content):
            for rect in page.search_for(phrase):
                page.add_highlight_annot(rect)
        png = page.get_pixmap(dpi=_PREVIEW_DPI).tobytes("png")
        doc.close()
        return png
    except Exception:  # noqa: BLE001 — preview nunca pode derrubar o chat
        return None
