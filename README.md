# DocRAG BR

RAG (Retrieval-Augmented Generation) para documentos financeiros brasileiros. Transforma PDFs densos — texto, tabelas, gráficos e infográficos — em dados pesquisáveis via chat, com **citação obrigatória da fonte** em toda resposta.

> Projeto desenvolvido para o **RAISE Summit Hackathon** (4-5 de julho de 2026) por Ryan Nishikawa.

## O problema

Empresas brasileiras perdem tempo e dinheiro extraindo manualmente informação de documentos densos (relatórios trimestrais, balanços, documentos CVM). Ferramentas de RAG genéricas só lidam bem com texto corrido — tabelas e gráficos ficam de fora.

## Como funciona

```
Documento (PDF)
      │
      ▼
┌─────────────────────────────────────┐
│        INGESTÃO MULTI-FORMATO        │
│  Texto   → chunking por sentença     │
│  Tabela  → pdfplumber → markdown     │
│  Gráfico → Vision LLM → descrição    │
└─────────────────────────────────────┘
      │
      ▼
Embeddings (sentence-transformers, multilíngue)
      │
      ▼
Vector store (ChromaDB, persistente)
      │
      ▼
┌─────────────────────────────────────┐
│      RETRIEVAL EM 2 ESTÁGIOS         │
│  1. Roteamento por intenção (LLM)    │
│  2. Reranking dos top chunks (LLM)   │
└─────────────────────────────────────┘
      │
      ▼
Resposta + citação da fonte (arquivo + página)
      │
      ▼
Chat (Streamlit)
```

Cada tipo de conteúdo é processado por um método dedicado. Todos os LLMs (visão, roteamento, reranking e resposta final) são acessados via **OpenRouter**.

## Stack

| Camada | Tecnologia |
|---|---|
| Extração de PDF | PyMuPDF (fitz) |
| Extração de tabelas | pdfplumber |
| Vision LLM (gráficos) | OpenRouter (`google/gemini-2.5-flash`) |
| Embeddings | `sentence-transformers` (multilíngue, local, sem custo) |
| Vector store | ChromaDB |
| Roteamento + reranking | LLM via OpenRouter |
| Resposta final | LLM via OpenRouter |
| Interface | Streamlit |

## Como rodar

Requer Python 3.11+.

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar a chave da OpenRouter
copy .env.example .env
# edite .env e preencha OPENROUTER_API_KEY

# 3. Colocar PDFs de teste em data/sample_docs/

# 4. Ingerir os documentos (texto + tabelas + gráficos → vector store)
python -m src.ingest

# 5. Abrir o chat
streamlit run src/chat/app.py
```

## Estrutura do repositório

```
docrag-br/
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py               # configuração central
│   ├── ingestion/
│   │   ├── text_chunker.py     # texto → chunks por sentença
│   │   ├── table_extractor.py  # tabelas → markdown
│   │   └── vision_processor.py # gráficos → descrição via Vision LLM
│   ├── embeddings/
│   │   └── embedder.py         # embeddings + ChromaDB
│   ├── retrieval/
│   │   ├── router.py           # estágio 1: roteamento por intenção
│   │   └── reranker.py         # estágio 2: reranking via LLM
│   └── chat/
│       └── app.py              # interface Streamlit
├── data/
│   └── sample_docs/            # documentos de teste (B3/CVM)
└── demo/
    └── demo_video.mp4          # vídeo demo de 1 minuto
```

## Visão pós-hackathon

- Chunker de tabelas auto-contido avançado
- Pipeline de visão multi-página robusto
- Índice híbrido (denso + BM25)
- Reranker treinado/custom
- UIs separadas por persona (analista de equity, contador/auditor, diretor financeiro)
