"""Extracao de tabelas de PDFs com pdfplumber, serializadas como markdown."""
import pdfplumber


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


def extract_table_chunks(pdf_path: str) -> list[dict]:
    """Retorna cada tabela do PDF como um chunk markdown com metadados."""
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for idx, table in enumerate(page.extract_tables(), start=1):
                md = _table_to_markdown(table)
                if not md:
                    continue
                results.append(
                    {
                        "content": f"Tabela {idx} (pagina {page_num}):\n{md}",
                        "type": "table",
                        "source": pdf_path,
                        "page": page_num,
                    }
                )
    return results
