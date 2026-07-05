"""Pipeline de consulta: roteamento -> busca densa -> reranking -> resposta com citacao."""
from collections.abc import Iterator

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
3. {language_rule}
4. Ao citar valores, reproduza-os EXATAMENTE como aparecem na fonte — nunca arredonde, nunca converta unidades, mantenha o mesmo formato (ex: se a fonte diz "61.412", escreva "61.412", nao "61,4 mil"). Cada numero da sua resposta sera auditado automaticamente contra a fonte.
5. Se a pergunta envolver comparacao entre documentos, empresas ou periodos, organize os valores em uma tabela markdown comparativa, citando a fonte de cada valor.

Fontes:
{sources}

Pergunta: {query}"""

# a regra de idioma reforca o formato numerico BR: o verificador so entende
# "61.412" / "4,2%" — se o modelo converter para formato ingles, a auditoria
# marcaria falso ⚠️
LANGUAGE_RULES = {
    "pt": "Responda em portugues, de forma direta e profissional.",
    "en": (
        "Answer in ENGLISH, direct and professional. Even in English, reproduce "
        "every numeric value EXACTLY as it appears in the source, keeping the "
        'Brazilian number format (e.g. "61.412", "4,2%", "R$ 44,0") — NEVER '
        "convert numbers to English formatting."
    ),
}

NO_INDEX_MESSAGES = {
    "pt": (
        "Nenhum documento indexado ainda. Rode a ingestao primeiro "
        "(`python -m src.ingest`)."
    ),
    "en": (
        "No documents indexed yet. Run the ingestion first "
        "(`python -m src.ingest`)."
    ),
}


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

    final = rerank(query, candidates, TOP_K_FINAL)
    # o roteamento e um contrato com o usuario: se ele pediu grafico/tabela,
    # o reranker nao pode descartar todos os chunks desse tipo
    if preferred_type and not any(c["type"] == preferred_type for c in final):
        typed = [c for c in candidates if c["type"] == preferred_type]
        if typed:
            final = typed[:2] + final[: TOP_K_FINAL - 2]
    return final


def _build_sources(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"--- Fonte: [{c['source']}, pag. {c['page']}] (tipo: {c['type']}) ---\n{c['content']}"
        for c in chunks
    )


def answer_stream(query: str, lang: str = "pt") -> tuple[Iterator[str], list[dict]]:
    """Retorna (gerador de tokens da resposta, chunks usados como fonte).

    O retrieval roda antes (sincrono) para a UI poder exibir as fontes; a
    resposta chega em streaming. `lang` controla o idioma da resposta ("pt"
    ou "en") — os numeros permanecem no formato BR da fonte em ambos.
    """
    chunks = search(query)
    if not chunks:
        return iter([NO_INDEX_MESSAGES.get(lang, NO_INDEX_MESSAGES["pt"])]), []

    prompt = ANSWER_PROMPT.format(
        sources=_build_sources(chunks),
        query=query,
        language_rule=LANGUAGE_RULES.get(lang, LANGUAGE_RULES["pt"]),
    )

    def _generate() -> Iterator[str]:
        stream = _client().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=3000,
            stream=True,
        )
        for event in stream:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content

    return _generate(), chunks


def answer(query: str, lang: str = "pt") -> tuple[str, list[dict]]:
    """Versao sem streaming: retorna (resposta completa, chunks-fonte)."""
    stream, chunks = answer_stream(query, lang=lang)
    return "".join(stream).strip(), chunks
