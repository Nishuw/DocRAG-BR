"""Interface de chat do DocRAG BR (Streamlit).

Uso: streamlit run src/chat/app.py
"""
import base64
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import streamlit.components.v1 as components

from src.chat.pdf_preview import render_source_page
from src.config import OPENROUTER_API_KEY
from src.embeddings.embedder import get_collection
from src.rag import answer_stream
from src.verification.auditor import run_audit
from src.verification.verifier import annotate_answer, verify_answer

st.set_page_config(page_title="DocRAG BR", page_icon="🔎", layout="centered")

_CSS = """
<style>
/* containers com borda viram cards de verdade */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px;
    border: 1px solid rgba(49, 51, 63, 0.12);
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
    transition: box-shadow .15s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.10);
}
.stButton > button { border-radius: 10px; font-weight: 600; }
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(90deg, #0ea5e9 0%, #10b981 100%);
    border: none;
}
.docrag-hero {
    background: linear-gradient(120deg, #0f172a 0%, #134e4a 100%);
    border-radius: 18px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1rem;
    color: #f8fafc;
}
.docrag-hero h1 { color: #f8fafc; font-size: 2rem; margin: 0 0 .35rem 0; }
.docrag-hero p { color: #cbd5e1; margin: 0; font-size: .95rem; line-height: 1.5; }
.docrag-pill {
    display: inline-block; margin-top: .7rem; padding: .25rem .8rem;
    border-radius: 999px; font-size: .78rem; font-weight: 600;
    background: rgba(16, 185, 129, .18); color: #6ee7b7;
    border: 1px solid rgba(16, 185, 129, .4);
}
.docrag-badge {
    display: inline-block; padding: .15rem .6rem; border-radius: 999px;
    font-size: .72rem; font-weight: 700; letter-spacing: .04em;
}
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

# (fundo do badge, cor do texto) por severidade
_SEVERITY_STYLE = {
    "alerta": ("#fee2e2", "#b91c1c"),
    "atencao": ("#fef3c7", "#b45309"),
    "destaque": ("#ffedd5", "#c2410c"),
    "info": ("#dbeafe", "#1d4ed8"),
}

TEXTS = {
    "en": {
        "caption": (
            "The autonomous analyst that **audits the document**: every number is "
            "verified against the original source and every citation opens the real page."
        ),
        "type_label": {"text": "text", "table": "table", "image": "chart"},
        "suggested": [
            "What was the net income in 1T26?",
            "How did gross debt evolve in the quarter?",
            "What does the operating cash flow chart show?",
            "Summarize the main highlights of the quarter.",
        ],
        "try_asking": "**Or ask it yourself:**",
        "chat_placeholder": "E.g.: What was the net revenue in the quarter?",
        "audit_button": "🕵️ Audit document",
        "audit_help": (
            "The system reads the document on its own and flags inconsistencies "
            "between text, tables and charts."
        ),
        "audit_cta": "🕵️ What did the auditor find in this document?",
        "audit_spinner": "🕵️ Reading the document: cross-checking text, tables and charts...",
        "audit_error": "Audit error: ",
        "findings_header": "🕵️ What the auditor found — without being asked",
        "findings_caption": (
            "The system read the document on its own and cross-checked what the "
            "**text claims** against what the **tables and charts show**. Only "
            "findings whose numbers were confirmed in the source (✅) make it here."
        ),
        "finding_audit": "Audit: {confirmed}/{total} numbers confirmed in the original document.",
        "see_page": "📄 See it on page {page} of the document",
        "page_caption": "Page {page} — cited excerpt highlighted in yellow",
        "no_preview": "Preview unavailable for this source.",
        "verif_ok": (
            "🔎 **Automatic audit:** {confirmed}/{total} numbers confirmed "
            "in the original document."
        ),
        "verif_warn": (
            "🔎 **Automatic audit:** {confirmed}/{total} numbers confirmed. "
            "Not found in the source: {missing} — double-check before using."
        ),
        "source_page_tab": "Original page",
        "source_text_tab": "Indexed content",
        "sidebar_index": "Index",
        "chunks_metric": "Indexed chunks",
        "empty_store": "Vector store empty.",
        "ingest_hint": "Run `python -m src.ingest` to index the PDFs in `data/sample_docs/`.",
        "no_key": "`OPENROUTER_API_KEY` not set in `.env` — answers disabled.",
        "how_it_works": (
            "**How every answer is verified**\n\n"
            "1. Intent routing (text / table / chart)\n"
            "2. LLM reranking\n"
            "3. ✅ Every number in the answer is audited against the source\n"
            "4. 📄 Every citation opens the real page with the excerpt highlighted\n\n"
            "Models via [OpenRouter](https://openrouter.ai)."
        ),
        "search_spinner": "Searching the documents...",
        "error_prefix": "Error processing the question: ",
        "hero_tagline": (
            "The autonomous analyst that audits the document — every number is "
            "verified against the source, every citation opens the real page."
        ),
        "hero_pill": "✅ Proof, not promise — every claim verified to the pixel",
        "severity_label": {
            "alerta": "ALERT",
            "atencao": "ATTENTION",
            "destaque": "HIGHLIGHT",
            "info": "INFO",
        },
        "fidelity": "Fidelity: {pct}% of the numbers confirmed in the source",
    },
    "pt": {
        "caption": (
            "O analista autônomo que **audita o documento**: cada número é verificado "
            "contra a fonte original e cada citação abre a página real."
        ),
        "type_label": {"text": "texto", "table": "tabela", "image": "gráfico"},
        "suggested": [
            "Qual foi o lucro líquido no 1T26?",
            "Como evoluiu a dívida bruta no trimestre?",
            "O que mostra o gráfico de fluxo de caixa operacional?",
            "Resuma os principais destaques do trimestre.",
        ],
        "try_asking": "**Ou pergunte você mesmo:**",
        "chat_placeholder": "Ex: Qual foi a receita líquida no trimestre?",
        "audit_button": "🕵️ Auditar documento",
        "audit_help": (
            "O sistema lê o documento sozinho e aponta inconsistências entre "
            "texto, tabelas e gráficos."
        ),
        "audit_cta": "🕵️ O que o auditor encontrou neste documento?",
        "audit_spinner": "🕵️ Lendo o documento: cruzando texto, tabelas e gráficos...",
        "audit_error": "Erro na auditoria: ",
        "findings_header": "🕵️ O que o auditor encontrou — sem ninguém perguntar",
        "findings_caption": (
            "O sistema leu o documento sozinho e cruzou o que o **texto afirma** com "
            "o que as **tabelas e gráficos mostram**. Só chega aqui a descoberta "
            "cujos números foram confirmados na fonte (✅)."
        ),
        "finding_audit": "Auditoria: {confirmed}/{total} números confirmados no documento original.",
        "see_page": "📄 Ver na página {page} do documento",
        "page_caption": "Página {page} — trecho citado destacado em amarelo",
        "no_preview": "Pré-visualização indisponível para esta fonte.",
        "verif_ok": (
            "🔎 **Auditoria automática:** {confirmed}/{total} números confirmados "
            "no documento original."
        ),
        "verif_warn": (
            "🔎 **Auditoria automática:** {confirmed}/{total} números confirmados. "
            "Não localizados na fonte: {missing} — confira antes de usar."
        ),
        "source_page_tab": "Página original",
        "source_text_tab": "Conteúdo indexado",
        "sidebar_index": "Índice",
        "chunks_metric": "Chunks indexados",
        "empty_store": "Vector store vazio.",
        "ingest_hint": "Rode `python -m src.ingest` para indexar os PDFs de `data/sample_docs/`.",
        "no_key": "`OPENROUTER_API_KEY` não configurada no `.env` — respostas desativadas.",
        "how_it_works": (
            "**Como cada resposta é verificada**\n\n"
            "1. Roteamento por intenção (texto / tabela / gráfico)\n"
            "2. Reranking via LLM\n"
            "3. ✅ Todo número da resposta é auditado contra a fonte\n"
            "4. 📄 Toda citação abre a página real com o trecho destacado\n\n"
            "Modelos via [OpenRouter](https://openrouter.ai)."
        ),
        "search_spinner": "Buscando nos documentos...",
        "error_prefix": "Erro ao processar a pergunta: ",
        "hero_tagline": (
            "O analista autônomo que audita o documento — cada número é verificado "
            "contra a fonte, cada citação abre a página real."
        ),
        "hero_pill": "✅ Prova, não promessa — cada afirmação verificada até o pixel",
        "severity_label": {
            "alerta": "ALERTA",
            "atencao": "ATENÇÃO",
            "destaque": "DESTAQUE",
            "info": "INFO",
        },
        "fidelity": "Fidelidade: {pct}% dos números confirmados na fonte",
    },
}


def _md_safe(text: str) -> str:
    """Escapa '$' para o markdown do Streamlit nao entrar em modo LaTeX (R$, US$)."""
    return text.replace("$", "\\$")


@st.cache_data(show_spinner=False, max_entries=64)
def _page_png(source: str, page: int, content: str) -> bytes | None:
    return render_source_page(source, page, content)


# --- sidebar (inclui o seletor de idioma, por isso vem antes do conteudo) ---
with st.sidebar:
    lang_label = st.radio(
        "🌐 Language / Idioma",
        ["English", "Português"],
        horizontal=True,
        key="lang_choice",
    )
    lang = "en" if lang_label == "English" else "pt"
    T = TEXTS[lang]
    st.divider()

    st.header(T["sidebar_index"])
    try:
        count = get_collection().count()
        st.metric(T["chunks_metric"], count)
    except Exception:
        count = 0
        st.warning(T["empty_store"])
    if count == 0:
        st.info(T["ingest_hint"])
    if not OPENROUTER_API_KEY:
        st.error(T["no_key"])
    st.divider()
    if st.button(
        T["audit_button"],
        use_container_width=True,
        type="primary",
        disabled=count == 0 or not OPENROUTER_API_KEY,
        help=T["audit_help"],
    ):
        st.session_state.trigger_audit = True
    st.divider()
    st.markdown(T["how_it_works"])


st.markdown(
    f"""
<div class="docrag-hero">
  <h1>🔎 DocRAG BR</h1>
  <p>{T["hero_tagline"]}</p>
  <span class="docrag-pill">{T["hero_pill"]}</span>
</div>
""",
    unsafe_allow_html=True,
)


def _render_verification(v: dict) -> None:
    if not v or v["total"] == 0:
        return
    ratio = v["confirmed"] / v["total"]
    st.progress(ratio, text=T["fidelity"].format(pct=round(ratio * 100)))
    if v["confirmed"] == v["total"]:
        st.success(T["verif_ok"].format(confirmed=v["confirmed"], total=v["total"]))
    else:
        missing = ", ".join(f"`{n['raw']}`" for n in v["numbers"] if not n["verified"])
        st.warning(
            T["verif_warn"].format(
                confirmed=v["confirmed"], total=v["total"], missing=missing
            )
        )


def _render_page_image(source: str, page: int, content: str) -> None:
    png = _page_png(source, page, content)
    if png:
        st.image(
            png,
            caption=T["page_caption"].format(page=page),
            use_column_width=True,
        )
    else:
        st.info(T["no_preview"])


_VIEWER_TEMPLATE = """
<div id="drv">
<style>
  #drv * { box-sizing: border-box; margin: 0; padding: 0; }
  #drv {
    font-family: "Source Sans Pro", -apple-system, "Segoe UI", sans-serif;
    display: flex; gap: 14px; height: 620px;
    background: linear-gradient(120deg, #0f172a 0%, #134e4a 100%);
    border-radius: 18px; padding: 14px;
  }
  #drv .list { width: 40%; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
  #drv .item {
    background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12);
    border-radius: 12px; padding: 12px; cursor: pointer;
    transition: background .15s, border-color .15s; color: #e2e8f0;
  }
  #drv .item:hover { background: rgba(255,255,255,.13); }
  #drv .item.active { background: rgba(16,185,129,.16); border-color: #10b981; }
  #drv .badge {
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: 10px; font-weight: 700; letter-spacing: .05em; margin-bottom: 7px;
  }
  #drv .title { font-weight: 700; font-size: 13px; line-height: 1.35; }
  #drv .fid { margin-top: 7px; font-size: 11px; color: #6ee7b7; }
  #drv .stage { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
  #drv .pagewrap {
    flex: 1; overflow: auto; border-radius: 12px; background: #1e293b;
  }
  #drv .pagewrap img { width: 100%; height: auto; border-radius: 12px; display: block; }
  #drv .placeholder {
    height: 100%; display: none; align-items: center; justify-content: center;
    color: #64748b; font-size: 13px;
  }
  #drv .detail {
    background: rgba(255,255,255,.07); border-radius: 12px; padding: 12px;
    color: #e2e8f0; font-size: 12.5px; line-height: 1.55;
    max-height: 175px; overflow-y: auto;
  }
  #drv .pageref { font-size: 11px; color: #94a3b8; margin-top: 7px; }
  #drv ::-webkit-scrollbar { width: 8px; height: 8px; }
  #drv ::-webkit-scrollbar-thumb { background: rgba(255,255,255,.18); border-radius: 4px; }
  #drv ::-webkit-scrollbar-track { background: transparent; }
</style>
<div class="list">__ITEMS__</div>
<div class="stage">
  <div class="pagewrap">
    <img id="drv-img" src="" alt="">
    <div class="placeholder" id="drv-ph">__NO_PREVIEW__</div>
  </div>
  <div class="detail">
    <div id="drv-text"></div>
    <div class="pageref" id="drv-ref"></div>
  </div>
</div>
</div>
<script>
const F = __DATA__;
function sel(i) {
  document.querySelectorAll("#drv .item").forEach(function (e, j) {
    e.classList.toggle("active", j === i);
  });
  const img = document.getElementById("drv-img");
  const ph = document.getElementById("drv-ph");
  if (F[i].img) {
    img.src = F[i].img;
    img.style.display = "block";
    ph.style.display = "none";
  } else {
    img.style.display = "none";
    ph.style.display = "flex";
  }
  document.getElementById("drv-text").innerHTML = F[i].text;
  document.getElementById("drv-ref").textContent = F[i].ref;
}
sel(0);
</script>
"""


def _findings_viewer_html(findings: list[dict]) -> str:
    """Monta o visualizador interativo: lista de descobertas + pagina real."""
    items, data = [], []
    for i, f in enumerate(findings):
        sev = str(f.get("severidade", "")).lower()
        bg, fg = _SEVERITY_STYLE.get(sev, _SEVERITY_STYLE["info"])
        label = T["severity_label"].get(sev, "INFO")
        v = f["verification"]
        fid = (
            T["finding_audit"].format(confirmed=v["confirmed"], total=v["total"])
            if v["total"]
            else ""
        )
        png = None
        if f.get("arquivo") and f.get("pagina"):
            png = _page_png(f["arquivo"], f["pagina"], f.get("trecho", ""))
        img = f"data:image/png;base64,{base64.b64encode(png).decode()}" if png else ""
        items.append(
            f'<div class="item" onclick="sel({i})">'
            f'<span class="badge" style="background:{bg};color:{fg}">{label}</span>'
            f'<div class="title">{html.escape(f["titulo"])}</div>'
            f'<div class="fid">{fid}</div></div>'
        )
        data.append(
            {
                "img": img,
                "text": html.escape(f["descoberta_anotada"]).replace("**", ""),
                "ref": f'{f.get("arquivo", "")} — p. {f.get("pagina", "")}',
            }
        )
    # "<\\/" evita fechar o <script> se algum texto contiver "</"
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        _VIEWER_TEMPLATE
        .replace("__ITEMS__", "".join(items))
        .replace("__DATA__", payload)
        .replace("__NO_PREVIEW__", html.escape(T["no_preview"]))
    )


def _render_findings(findings: list[dict]) -> None:
    st.subheader(T["findings_header"])
    st.caption(T["findings_caption"])
    components.html(_findings_viewer_html(findings), height=650, scrolling=False)


def _render_sources(chunks: list[dict]) -> None:
    for c in chunks:
        label = T["type_label"].get(c["type"], c["type"])
        with st.expander(f"📄 {c['source']}, pag. {c['page']} ({label})"):
            tab_page, tab_text = st.tabs([T["source_page_tab"], T["source_text_tab"]])
            with tab_page:
                _render_page_image(c["source"], c["page"], c["content"])
            with tab_text:
                st.markdown(_md_safe(c["content"]))


if "messages" not in st.session_state:
    st.session_state.messages = []

user_prompt = st.chat_input(T["chat_placeholder"])
if not user_prompt:
    user_prompt = st.session_state.pop("pending_prompt", None)

# auditoria autonoma: o sistema fala primeiro
if st.session_state.pop("trigger_audit", False):
    with st.spinner(T["audit_spinner"]):
        try:
            st.session_state.audit_findings = run_audit(lang=lang)
        except Exception as exc:  # noqa: BLE001
            st.error(f"{T['audit_error']}{exc}")

if st.session_state.get("audit_findings"):
    _render_findings(st.session_state.audit_findings)
    st.divider()

# primeira visita: CTA da auditoria + perguntas sugeridas
if not st.session_state.messages and not user_prompt:
    if not st.session_state.get("audit_findings"):
        if st.button(
            T["audit_cta"],
            use_container_width=True,
            type="primary",
            disabled=count == 0 or not OPENROUTER_API_KEY,
        ):
            st.session_state.trigger_audit = True
            st.rerun()
    st.markdown(T["try_asking"])
    cols = st.columns(2)
    for i, q in enumerate(T["suggested"]):
        if cols[i % 2].button(q, use_container_width=True, key=f"sugg_{i}"):
            st.session_state.pending_prompt = q
            st.rerun()

# historico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(_md_safe(msg["content"]))
        _render_verification(msg.get("verification"))
        if msg.get("sources"):
            _render_sources(msg["sources"])

if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(_md_safe(user_prompt))

    with st.chat_message("assistant"):
        try:
            with st.spinner(T["search_spinner"]):
                stream, chunks = answer_stream(user_prompt, lang=lang)
            placeholder = st.empty()
            with placeholder.container():
                full_text = st.write_stream(stream)
            full_text = str(full_text).strip()

            verification = verify_answer(full_text, chunks)
            annotated = annotate_answer(full_text, verification["numbers"])
            placeholder.markdown(_md_safe(annotated))

            _render_verification(verification)
            if chunks:
                _render_sources(chunks)
        except Exception as exc:  # noqa: BLE001
            annotated = f"{T['error_prefix']}{exc}"
            verification, chunks = None, []
            st.error(annotated)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": annotated,
            "sources": chunks,
            "verification": verification,
        }
    )
