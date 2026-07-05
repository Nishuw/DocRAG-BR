"""Descricao de graficos/infograficos via Vision LLM (OpenRouter).

Graficos em relatorios financeiros modernos sao majoritariamente desenhos
VETORIAIS — invisiveis para page.get_images(). Por isso a unidade enviada ao
Vision LLM e a PAGINA INTEIRA renderizada: uma pagina e candidata se contem
imagem raster relevante OU muitos desenhos vetoriais. As paginas com maior
pontuacao (ate MAX_VISION_PAGES_PER_DOC) sao descritas em uma chamada cada.
"""
import base64

import fitz
from openai import OpenAI

from src.config import (
    MAX_VISION_PAGES_PER_DOC,
    MIN_CHART_PALETTE_COLORS,
    MIN_IMAGE_SIZE_PX,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    VISION_MODEL,
    VISION_PAGE_DPI,
)

VISION_PROMPT = """Voce esta analisando a PAGINA COMPLETA de um documento financeiro brasileiro.
Descreva em portugues TODOS os graficos e infograficos visiveis nesta pagina:
titulo de cada grafico, eixos, valores numericos, periodos, tendencias e conclusoes.
Seja exaustivo com os numeros — essa descricao sera usada para responder perguntas depois.
Reproduza os valores exatamente como aparecem (mesmo formato e unidade).
Ignore texto corrido e tabelas simples: eles ja foram extraidos por outro processo.
Se a pagina NAO contiver nenhum grafico ou infografico, responda apenas: IRRELEVANTE."""


def _client() -> OpenAI:
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def describe_image(image_bytes: bytes, mime: str = "image/png") -> str:
    b64 = base64.b64encode(image_bytes).decode()
    response = _client().chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
        # explicito: sem isso a OpenRouter assume o maximo do modelo (65k) e
        # contas com pouco credito recebem 402 antes mesmo de gerar
        max_tokens=4000,
    )
    return (response.choices[0].message.content or "").strip()


def _saturated(color) -> bool:
    """Cor de preenchimento que nao e branco/preto/cinza."""
    if not color:
        return False
    r, g, b = color[:3]
    return (max(r, g, b) - min(r, g, b)) > 0.15


def _page_chart_score(page: fitz.Page) -> int:
    """Pontua a chance da pagina conter graficos.

    Contar desenhos vetoriais engana: paginas de TABELA tem centenas de tracos
    (bordas, zebrado) e venciam paginas de grafico reais. Sinal melhor: graficos
    usam uma PALETA rica (varias cores de preenchimento distintas — barras,
    series, legendas), tabelas usam 1-2 cores; e, entre paginas de paleta
    parecida, a tabela tem muito mais desenhos que o grafico.
    """
    raster = sum(
        1
        for img in page.get_images(full=True)
        if img[2] >= MIN_IMAGE_SIZE_PX and img[3] >= MIN_IMAGE_SIZE_PX
    )
    drawings = page.get_drawings()
    palette = {
        tuple(round(c, 1) for c in d["fill"][:3])
        for d in drawings
        if d.get("fill") and _saturated(d["fill"])
    }
    if raster == 0 and len(palette) < MIN_CHART_PALETTE_COLORS:
        return 0
    # paleta rica puxa para cima; excesso de desenhos (cara de tabela) puxa
    # para baixo no desempate
    return raster * 1000 + len(palette) * 100 - min(len(drawings) // 10, 99)


def select_chart_pages(doc: fitz.Document) -> list[int]:
    """Indices (0-based) das paginas candidatas, limitado ao orcamento de visao."""
    scored = [(idx, _page_chart_score(page)) for idx, page in enumerate(doc)]
    candidates = [(idx, s) for idx, s in scored if s > 0]
    candidates.sort(key=lambda t: t[1], reverse=True)
    chosen = sorted(idx for idx, _ in candidates[:MAX_VISION_PAGES_PER_DOC])
    return chosen


def extract_image_chunks(pdf_path: str) -> list[dict]:
    """Renderiza paginas com graficos e gera descricoes textuais via Vision LLM."""
    doc = fitz.open(pdf_path)
    results = []
    for idx in select_chart_pages(doc):
        page = doc[idx]
        page_num = idx + 1
        image_bytes = page.get_pixmap(dpi=VISION_PAGE_DPI).tobytes("png")
        try:
            description = describe_image(image_bytes)
        except Exception as exc:  # noqa: BLE001 — nao derruba a ingestao inteira
            print(f"[vision] erro na pagina {page_num}: {exc}")
            continue
        if "IRRELEVANTE" in description.upper()[:30]:
            continue
        results.append(
            {
                "content": f"Graficos da pagina {page_num}:\n{description}",
                "type": "image",
                "source": pdf_path,
                "page": page_num,
            }
        )
    doc.close()
    return results
