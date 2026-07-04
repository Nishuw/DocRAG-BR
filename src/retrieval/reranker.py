"""Estagio 2: reranking dos chunks candidatos via LLM (OpenRouter)."""
import json
import re

from openai import OpenAI

from src.config import LLM_MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL

RERANK_PROMPT = """Voce e um reranker. Dada uma pergunta e uma lista de trechos numerados de documentos financeiros, retorne os indices dos {top_k} trechos MAIS relevantes para responder a pergunta, em ordem decrescente de relevancia.

Responda APENAS com uma lista JSON de indices. Exemplo: [2, 0, 5, 1]

Pergunta: {query}

Trechos:
{passages}"""


def _client() -> OpenAI:
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Reordena candidatos por relevancia. Em caso de falha, mantem a ordem densa."""
    if len(candidates) <= top_k:
        return candidates

    passages = "\n\n".join(
        f"[{i}] ({c['type']}, pag. {c['page']}) {c['content'][:500]}"
        for i, c in enumerate(candidates)
    )
    try:
        response = _client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": RERANK_PROMPT.format(
                        top_k=top_k, query=query, passages=passages
                    ),
                }
            ],
            max_tokens=100,
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip()
        match = re.search(r"\[[\d,\s]*\]", text)
        indices = json.loads(match.group()) if match else []
        valid = [i for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
        if valid:
            return [candidates[i] for i in valid[:top_k]]
    except Exception as exc:  # noqa: BLE001 — fallback para ordem da busca densa
        print(f"[reranker] falha, usando ordem densa: {exc}")
    return candidates[:top_k]
