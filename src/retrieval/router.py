"""Estagio 1: roteamento por intencao — classifica a pergunta e prioriza o tipo de conteudo."""
from openai import OpenAI

from src.config import LLM_MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL

ROUTER_PROMPT = """Classifique a pergunta de um usuario sobre documentos financeiros em UMA das categorias:

- TABELA: pergunta sobre valores especificos, linhas de balanco, demonstrativos, comparativos numericos detalhados
- GRAFICO: pergunta sobre tendencias, evolucao visual, graficos ou infograficos
- TEXTO: pergunta conceitual, contexto, explicacoes, notas explicativas
- GERAL: pergunta ampla que pode envolver qualquer tipo de conteudo

Responda APENAS com a palavra da categoria.

Pergunta: {query}"""

_CATEGORY_TO_TYPE = {"TABELA": "table", "GRAFICO": "image", "TEXTO": "text"}


def _client() -> OpenAI:
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def route_intent(query: str) -> str | None:
    """Retorna o tipo de conteudo prioritario ('table', 'image', 'text') ou None (geral)."""
    try:
        response = _client().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": ROUTER_PROMPT.format(query=query)}],
            max_tokens=10,
            temperature=0,
        )
        category = (response.choices[0].message.content or "").strip().upper()
    except Exception:  # noqa: BLE001 — roteamento e otimizacao, nao pode travar a busca
        return None
    return _CATEGORY_TO_TYPE.get(category)
