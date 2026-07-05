"""Verificador numerico: audita cada numero da resposta contra os chunks-fonte.

Todo valor numerico relevante que o LLM escreve na resposta e procurado nos
chunks usados como fonte. O resultado alimenta os selos de verificacao da UI
(confirmado na fonte / nao localizado) e a taxa de fidelidade da resposta.
"""
import re

# Regioes ignoradas na extracao: citacoes [arquivo, pag. X] e trimestres (1T26, 4T25)
_CITATION_RE = re.compile(r"\[[^\[\]]{0,150}?pag\.?\s*\d+[^\[\]]{0,20}\]", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\b\d[TQ]\d{2}\b", re.IGNORECASE)

# Numeros em formato BR: 61.412 | 61.412,5 | 61,4 | 4,2% | 2026
# O ponto so e aceito como separador de milhar (grupos de 3), entao "61.412" -> 61412.
_NUMBER_RE = re.compile(r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)%?")

_CURRENCY_PREFIX_RE = re.compile(r"(?:R\$|US\$|U\$|€)\s*$")


def _to_float(raw: str) -> float:
    return float(raw.rstrip("%").replace(".", "").replace(",", "."))


def _masked_spans(text: str) -> list[tuple[int, int]]:
    spans = [m.span() for m in _CITATION_RE.finditer(text)]
    spans += [m.span() for m in _QUARTER_RE.finditer(text)]
    return spans


def _inside(span: tuple[int, int], regions: list[tuple[int, int]]) -> bool:
    s, e = span
    return any(s >= a and e <= b for a, b in regions)


def extract_numbers(text: str, significant_only: bool = True) -> list[dict]:
    """Extrai numeros com posicao no texto original.

    Com significant_only=True (usado na resposta), ignora inteiros pequenos e
    "soltos" ("2 estagios", "top 4") — so audita valores com cara de dado
    financeiro: moeda, percentual, decimal, milhar ou >= 1000 (anos, valores).
    """
    masked = _masked_spans(text)
    results = []
    for m in _NUMBER_RE.finditer(text):
        if _inside(m.span(), masked):
            continue
        raw = m.group()
        start, end = m.span()
        has_currency = bool(_CURRENCY_PREFIX_RE.search(text[max(0, start - 4):start]))
        is_significant = (
            has_currency
            or raw.endswith("%")
            or "," in raw
            or "." in raw
            or _to_float(raw) >= 1000
        )
        if significant_only and not is_significant:
            continue
        results.append(
            {"raw": raw, "start": start, "end": end, "value": _to_float(raw)}
        )
    return results


def _source_values(chunks: list[dict]) -> set[float]:
    values: set[float] = set()
    for chunk in chunks:
        for num in extract_numbers(chunk["content"], significant_only=False):
            values.add(num["value"])
    return values


def verify_answer(answer: str, chunks: list[dict]) -> dict:
    """Audita a resposta: cada numero e procurado nos chunks-fonte.

    Retorna {"numbers": [...], "total": N, "confirmed": K}. Cada item de
    numbers tem raw, start, end, value e verified.
    """
    numbers = extract_numbers(answer)
    source_values = _source_values(chunks)
    for num in numbers:
        num["verified"] = num["value"] in source_values
    confirmed = sum(1 for n in numbers if n["verified"])
    return {"numbers": numbers, "total": len(numbers), "confirmed": confirmed}


def annotate_answer(answer: str, numbers: list[dict]) -> str:
    """Insere o selo (✅ confirmado / ⚠️ nao localizado) apos cada numero."""
    annotated = answer
    for num in sorted(numbers, key=lambda n: n["start"], reverse=True):
        mark = "✅" if num["verified"] else "⚠️"
        annotated = annotated[: num["end"]] + mark + annotated[num["end"]:]
    return annotated
