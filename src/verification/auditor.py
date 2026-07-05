"""Auditoria autonoma: o sistema le o documento e aponta descobertas sem pergunta.

Inverte o fluxo classico de RAG (usuario pergunta -> sistema responde): na
auditoria, o proprio sistema interroga o documento, cruzando o que o texto
narrativo AFIRMA contra o que as tabelas e graficos MOSTRAM. Cada descoberta
passa pelo mesmo verificador numerico das respostas do chat — descoberta cujos
numeros nao existem na fonte e descartada antes de chegar ao usuario.
"""
import json
import re

from openai import OpenAI

from src.config import LLM_MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from src.embeddings.embedder import get_collection
from src.verification.verifier import annotate_answer, verify_answer

# Limite de contexto enviado ao LLM (gemini flash aguenta bem mais; isso
# controla custo/latencia). Tabelas e graficos tem prioridade sobre texto.
_MAX_SOURCE_CHARS = 120_000
_TYPE_PRIORITY = {"table": 0, "image": 1, "text": 2}

AUDIT_PROMPT = """Voce e um auditor senior de documentos financeiros brasileiros. Voce recebeu abaixo o conteudo extraido de um relatorio (texto narrativo, tabelas e descricoes de graficos, cada trecho com arquivo e pagina).

Sua tarefa: SEM nenhuma pergunta do usuario, aponte de 3 a 5 descobertas que um analista precisaria ver. Priorize, nesta ordem:
1. INCONSISTENCIAS: afirmacoes do texto narrativo que os numeros das tabelas/graficos nao sustentam (ex: texto diz "margem solida" mas a tabela mostra queda).
2. DESTAQUES: variacoes relevantes entre periodos que o texto minimiza ou nao comenta.
3. ATENCAO: afirmacoes qualitativas importantes sem numero que as sustente.

Regras OBRIGATORIAS:
- {language_rule}
- Reproduza todo numero EXATAMENTE como aparece na fonte (mesmo formato: "61.412", nao "61,4 mil"; "4,2%", nao "4.2%"). Cada numero sera auditado automaticamente contra a fonte e descobertas com numeros inventados serao DESCARTADAS.
- Cite a fonte de cada afirmacao no formato [arquivo, pag. X].
- Em "trecho", copie LITERALMENTE uma frase curta (5 a 12 palavras) do conteudo da pagina indicada, sem alterar nada — sera usada para destacar o trecho na pagina real.

Responda SOMENTE com um array JSON valido, sem texto antes ou depois, no formato:
[
  {{
    "titulo": "titulo curto da descoberta",
    "severidade": "alerta" | "atencao" | "info",
    "descoberta": "2 a 4 frases com os numeros exatos e citacoes [arquivo, pag. X]",
    "arquivo": "nome_do_arquivo.pdf",
    "pagina": 4,
    "trecho": "frase curta copiada literalmente da fonte"
  }}
]

Fontes:
{sources}"""

# mesmo em ingles os numeros ficam no formato BR da fonte — o verificador so
# entende "61.412" / "4,2%", e conversao geraria falso ⚠️
_LANGUAGE_RULES = {
    "pt": 'Escreva "titulo" e "descoberta" em portugues.',
    "en": (
        'Write ALL the prose of "titulo" and "descoberta" in ENGLISH — when the '
        "document says something, PARAPHRASE it in English instead of quoting the "
        "Portuguese verbatim. Exception: reproduce every numeric value EXACTLY in "
        'the Brazilian source format (e.g. "61.412", "4,2%", "R$ 44,0"), NEVER '
        'converted to English formatting — decimal comma stays a comma ("8,4", NOT '
        '"8.4"); and the "trecho" field must stay in the original Portuguese, '
        "copied literally."
    ),
}


def _client() -> OpenAI:
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def _load_chunks() -> list[dict]:
    """Todos os chunks do indice, com tabelas/graficos priorizados no corte."""
    collection = get_collection()
    res = collection.get(include=["documents", "metadatas"])
    chunks = [
        {
            "content": doc,
            "type": meta["type"],
            "source": meta["source"],
            "page": meta["page"],
        }
        for doc, meta in zip(res["documents"], res["metadatas"])
    ]
    chunks.sort(key=lambda c: (_TYPE_PRIORITY.get(c["type"], 3), c["page"]))
    selected, used = [], 0
    for c in chunks:
        if used + len(c["content"]) > _MAX_SOURCE_CHARS:
            break
        selected.append(c)
        used += len(c["content"])
    return selected


def _build_sources(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"--- Fonte: [{c['source']}, pag. {c['page']}] (tipo: {c['type']}) ---\n{c['content']}"
        for c in chunks
    )


def _parse_findings(raw: str) -> list[dict]:
    """Extrai o array JSON da resposta, tolerante a cercas de codigo."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    findings = []
    for item in data:
        if not isinstance(item, dict) or not item.get("descoberta"):
            continue
        try:
            item["pagina"] = int(item.get("pagina", 0))
        except (TypeError, ValueError):
            item["pagina"] = 0
        item.setdefault("titulo", "Descoberta")
        item.setdefault("severidade", "info")
        item.setdefault("arquivo", "")
        item.setdefault("trecho", "")
        findings.append(item)
    return findings


def run_audit(lang: str = "pt") -> list[dict]:
    """Audita o documento indexado e retorna descobertas verificadas.

    Cada descoberta traz: titulo, severidade, descoberta_anotada (com selos
    ✅/⚠️ por numero), verification (do verifier), arquivo, pagina e trecho.
    Descobertas em que NENHUM numero foi confirmado na fonte sao descartadas.
    `lang` ("pt"/"en") controla o idioma dos textos das descobertas.
    """
    chunks = _load_chunks()
    if not chunks:
        return []

    response = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": AUDIT_PROMPT.format(
                    sources=_build_sources(chunks),
                    language_rule=_LANGUAGE_RULES.get(lang, _LANGUAGE_RULES["pt"]),
                ),
            }
        ],
        temperature=0.2,
        max_tokens=4000,
    )
    findings = _parse_findings(response.choices[0].message.content or "")

    audited = []
    for f in findings:
        v = verify_answer(f["descoberta"], chunks)
        if v["total"] > 0 and v["confirmed"] == 0:
            continue  # nenhum numero comprovado: nao chega ao usuario
        f["verification"] = v
        f["descoberta_anotada"] = annotate_answer(f["descoberta"], v["numbers"])
        audited.append(f)
    return audited
