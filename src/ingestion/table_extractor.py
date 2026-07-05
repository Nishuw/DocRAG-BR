"""Extracao de tabelas de PDFs com pdfplumber, serializadas como markdown.

Cada tabela e prefixada com o texto imediatamente acima dela na pagina
(titulo/legenda, ex: "TABELA 19 - DEMONSTRACAO CONSOLIDADA..."). Sem isso o
chunk e so uma grade de numeros sem semantica — e a busca densa nao encontra.
"""
import pdfplumber

_CAPTION_HEIGHT_PT = 55   # faixa acima da tabela onde procurar o titulo
_CAPTION_MAX_CHARS = 200


def _table_to_markdown(table: list[list]) -> str:
    rows = [[("" if cell is None else str(cell).strip()) for cell in row] for row in table]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return ""
    header = rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in rows[1:]:
        # normaliza linhas com numero diferente de colunas
        row = (row + [""] * len(header))[: len(header)]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _caption_above(page, bbox: tuple) -> str:
    """Ultimas linhas de texto logo acima da tabela (provavel titulo/legenda)."""
    _, top, _, _ = bbox
    y0 = max(0, top - _CAPTION_HEIGHT_PT)
    if y0 >= top:
        return ""
    try:
        crop = page.crop((0, y0, page.width, top))
        text = (crop.extract_text() or "").strip()
    except Exception:  # noqa: BLE001 — legenda e enriquecimento, nunca bloqueia
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return " ".join(lines[-2:])[:_CAPTION_MAX_CHARS]


def extract_table_chunks(pdf_path: str) -> list[dict]:
    """Retorna cada tabela do PDF como um chunk markdown com titulo e metadados."""
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for idx, table in enumerate(page.find_tables(), start=1):
                md = _table_to_markdown(table.extract())
                if not md:
                    continue
                caption = _caption_above(page, table.bbox)
                header = f"Tabela {idx} (pagina {page_num})"
                if caption:
                    header += f" — {caption}"
                results.append(
                    {
                        "content": f"{header}:\n{md}",
                        "type": "table",
                        "source": pdf_path,
                        "page": page_num,
                    }
                )
    return results
