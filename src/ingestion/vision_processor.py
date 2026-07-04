"""Descricao de graficos/infograficos via Vision LLM (OpenRouter)."""
import base64

import fitz
from openai import OpenAI

from src.config import (
    MAX_IMAGES_PER_DOC,
    MIN_IMAGE_SIZE_PX,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    VISION_MODEL,
)

VISION_PROMPT = """Voce esta analisando uma imagem extraida de um documento financeiro brasileiro.
Se for um grafico, tabela visual ou infografico, descreva em portugues TODOS os dados visiveis:
titulos, eixos, valores numericos, periodos, tendencias e conclusoes.
Seja exaustivo com os numeros — essa descricao sera usada para responder perguntas depois.
Se a imagem for decorativa (logo, foto, icone), responda apenas: IRRELEVANTE."""


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
    )
    return (response.choices[0].message.content or "").strip()


def extract_image_chunks(pdf_path: str) -> list[dict]:
    """Extrai imagens do PDF e gera descricoes textuais via Vision LLM."""
    doc = fitz.open(pdf_path)
    results = []
    processed = 0
    for page_num, page in enumerate(doc, start=1):
        if processed >= MAX_IMAGES_PER_DOC:
            break
        for img in page.get_images(full=True):
            if processed >= MAX_IMAGES_PER_DOC:
                break
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.width < MIN_IMAGE_SIZE_PX or pix.height < MIN_IMAGE_SIZE_PX:
                continue
            if pix.colorspace and pix.colorspace.n > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            image_bytes = pix.tobytes("png")
            try:
                description = describe_image(image_bytes)
            except Exception as exc:  # noqa: BLE001 — nao derruba a ingestao inteira
                print(f"[vision] erro na pagina {page_num}: {exc}")
                continue
            processed += 1
            if "IRRELEVANTE" in description.upper()[:30]:
                continue
            results.append(
                {
                    "content": f"Descricao de grafico/imagem (pagina {page_num}):\n{description}",
                    "type": "image",
                    "source": pdf_path,
                    "page": page_num,
                }
            )
    doc.close()
    return results
