"""Interface de chat do DocRAG BR (Streamlit).

Uso: streamlit run src/chat/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.embeddings.embedder import get_collection
from src.rag import answer

st.set_page_config(page_title="DocRAG BR", page_icon="📊", layout="centered")

st.title("📊 DocRAG BR")
st.caption(
    "Pergunte sobre seus documentos financeiros — texto, tabelas e gráficos. "
    "Toda resposta cita a fonte."
)

with st.sidebar:
    st.header("Índice")
    try:
        count = get_collection().count()
        st.metric("Chunks indexados", count)
    except Exception:
        count = 0
        st.warning("Vector store vazio.")
    if count == 0:
        st.info("Rode `python -m src.ingest` para indexar os PDFs de `data/sample_docs/`.")
    st.divider()
    st.markdown(
        "**Retrieval em 2 estágios**\n\n"
        "1. Roteamento por intenção (texto / tabela / gráfico)\n"
        "2. Reranking via LLM\n\n"
        "Modelos via [OpenRouter](https://openrouter.ai)."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for src_item in msg.get("sources", []):
            with st.expander(
                f"Fonte: {src_item['source']}, pág. {src_item['page']} ({src_item['type']})"
            ):
                st.markdown(src_item["content"])

if prompt := st.chat_input("Ex: Qual foi a receita líquida no trimestre?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Buscando nos documentos..."):
            try:
                reply, chunks = answer(prompt)
            except Exception as exc:  # noqa: BLE001
                reply, chunks = f"Erro ao processar a pergunta: {exc}", []
        st.markdown(reply)
        for c in chunks:
            with st.expander(f"Fonte: {c['source']}, pág. {c['page']} ({c['type']})"):
                st.markdown(c["content"])

    st.session_state.messages.append(
        {"role": "assistant", "content": reply, "sources": chunks}
    )
