"""Pipeline de consulta: roteamento -> busca densa -> reranking -> resposta com citacao."""
from openai import OpenAI

from src.config import (
    LLM_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    TOP_K_FINAL,
    TOP_K_RETRIEVAL,
)
from src.embeddings.embedder import query_chunks
from src.retrieval.reranker import rerank
from src.retrieval.router import route_intent

ANSWER_PROMPT = """Voce e um assistente especializado em documentos financeiros brasileiros, atendendo analistas de equity, contadores e diretores financeiros.

Responda a pergunta usando SOMENTE as fontes abaixo. Regras:
1. TODA afirmacao deve citar a fonte no formato [arquivo, pag. X].
2. Se as fontes nao contem a resposta, diga isso claramente — nunca invente.
3. Responda em portugues, de forma direta e profissional.
4. Ao citar valores, reproduza-os exatamente como aparecem na fonte.

Fontes:
{sources}

Pergunta: {query}"""


def _client() -> OpenAI:
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def search(query: str) -> list[dict]:
    """Retrieval em 2 estagios: roteamento por intencao + reranking."""
    preferred_type = route_intent(query)

    candidates = query_chunks(query, TOP_K_RETRIEVAL, content_type=preferred_type)
    # se o filtro por tipo retornar pouco, complementa com busca geral
    if preferred_type and len(candidates) < TOP_K_FINAL:
        seen = {c["content"] for c in candidates}
        extra = query_chunks(query, TOP_K_RETRIEVAL)
        candidates += [c for c in extra if c["content"] not in seen]

    return rerank(query, candidates, TOP_K_FINAL)


def answer(query: str) -> tuple[str, list[dict]]:
    """Retorna (resposta com citacoes, chunks usados como fonte)."""
    chunks = search(query)
    if not chunks:
        return (
            "Nenhum documento indexado ainda. Rode a ingestao primeiro "
            "(`python -m src.ingest`).",
            [],
        )

    sources = "\n\n".join(
        f"--- Fonte: [{c['source']}, pag. {c['page']}] (tipo: {c['type']}) ---\n{c['content']}"
        for c in chunks
    )
    response = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "user", "content": ANSWER_PROMPT.format(sources=sources, query=query)}
        ],
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip(), chunks
