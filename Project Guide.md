# DocRAG BR — Guia Mestre do Projeto
**RAISE Summit Hackathon — 4-5 Julho 2026 | Participante remoto: Ryan Nishikawa (solo)**

> Este arquivo é a fonte única de verdade do projeto. Use-o no Cursor como contexto para guiar todas as decisões técnicas até o deadline.

---

## 1. Visão do Produto

**O quê:** Sistema de RAG (Retrieval-Augmented Generation) voltado para empresas brasileiras, que transforma documentos financeiros complexos — texto, tabelas, gráficos e infográficos — em dados estruturados e pesquisáveis via chat.

**Por quê:** Empresas brasileiras perdem tempo e dinheiro extraindo manualmente informação de documentos densos (relatórios financeiros, balanços, laudos). Ferramentas de RAG genéricas não lidam bem com tabelas e gráficos — só texto.

**Para quem:**
- Analistas de equity
- Contadores/auditores
- Diretores financeiros não-técnicos

**Diferencial:** Pipeline de ingestão multi-formato (cada tipo de conteúdo processado por um método dedicado) + retrieval em dois estágios com citação obrigatória da fonte.

---

## 2. Arquitetura (visão geral)

```
Documento (PDF/imagem)
      │
      ▼
┌─────────────────────────────┐
│      INGESTÃO MULTI-FORMATO  │
│                              │
│  Texto  → chunking p/ sentença
│  Tabela → extração dedicada
│  Gráfico/Infográfico → Vision LLM → descrição textual
└─────────────────────────────┘
      │
      ▼
   Embeddings (denso)
      │
      ▼
   Vector Store (pgvector / Chroma / FAISS)
      │
      ▼
┌─────────────────────────────┐
│   RETRIEVAL EM 2 ESTÁGIOS    │
│  1. Roteamento por intenção  │
│  2. Reranking dos top chunks │
└─────────────────────────────┘
      │
      ▼
  Resposta + Citação da fonte
      │
      ▼
      Chat (interface única)
```

---

## 3. Escopo do MVP (o que fazer AGORA vs depois)

| Componente | MVP (hackathon) | Pós-hackathon (mencionar como visão) |
|---|---|---|
| Ingestão texto | ✅ Chunking por sentença | — |
| Ingestão tabelas | ✅ Extração simples (pdfplumber/camelot) | Chunker auto-contido avançado |
| Ingestão gráficos | ✅ 1 chamada por imagem via Vision LLM | Pipeline multi-página robusto |
| Índice vetorial | ✅ Embedding denso simples | Índice híbrido (denso + BM25) |
| Retrieval | ✅ Roteamento simples + reranking básico | Reranker treinado/custom |
| Citação de fontes | ✅ Obrigatório em toda resposta | — |
| Interface | ✅ 1 chat único, respostas adaptadas por prompt | UIs separadas por persona |

**Regra de ouro:** algo funcional ponta a ponta > sistema ambicioso pela metade.

---

## 4. Stack Técnica

- **Ingestão PDF:** `PyMuPDF` (fitz) ou `unstructured`
- **Extração de tabelas:** `pdfplumber` ou `camelot-py`
- **Vision LLM (gráficos/infográficos):** via **OpenRouter** (qualifica bônus) — ex: modelo com visão
- **Embeddings:** OpenAI/Voyage embeddings ou `sentence-transformers` (local, sem custo)
- **Vector store:** `pgvector` (Postgres) — Ryan já tem experiência com Postgres — ou Chroma/FAISS se quiser ir mais rápido
- **Roteamento de intenção + reranking:** LLM via OpenRouter com prompt de classificação
- **Backend:** Python (FastAPI, se der tempo) ou script direto
- **Frontend:** Streamlit (mais rápido) ou Next.js básico
- **LLM de resposta final:** via OpenRouter (mesmo provider, simplifica)

> 💡 Usar **OpenRouter** como camada de acesso a todos os modelos qualifica automaticamente para o bônus prize track do OpenRouter.

---

## 5. Dados de Teste

Usar documento(s) real(is) do mercado brasileiro para a demo ser convincente:
- Relatório financeiro trimestral de empresa listada na B3, ou
- Documento da CVM, ou
- Balanço patrimonial com gráficos/tabelas

**TODO:** escolher e baixar 1-2 documentos antes de começar a codar.

---

## 6. Plano de Horas

### Dia 1 — Sábado 4/7
| Horário | Tarefa |
|---|---|
| 12:00–15:00 | Pipeline de ingestão (texto + tabelas) funcionando ponta a ponta com 1-2 documentos |
| 15:00–18:00 | Integrar Vision LLM para gráficos → gerar embeddings → subir no vector store |
| 18:00–22:00 | Retrieval básico funcionando (query → chunks relevantes retornados) |

### Dia 2 — Domingo 5/7 (deadline 12:00 em ponto)
| Horário | Tarefa |
|---|---|
| 08:00–09:30 | Roteamento de intenção + reranking |
| 09:30–10:30 | Citação de fontes na resposta final |
| 10:30–11:30 | Interface de chat + polish visual |
| 11:30–12:00 | **Buffer de segurança** — gravar demo de 1 min, revisar submissão |

---

## 7. Checklist de Submissão (Cerebral Valley)

- [ ] Team Name definido
- [ ] Confirmar: participação **Remotely**
- [ ] Confirmar track (Cursor, Vultr, Crusoe ou **Google** — verificar problem statements antes de decidir)
- [ ] Project Description preenchida
- [ ] Repositório **GitHub público** criado e atualizado
- [ ] README completo no repo (ver seção 8)
- [ ] Vídeo demo de **1 minuto** gravado e no ar
- [ ] Marcar bônus track: **OpenRouter** (se usado na stack)
- [ ] Enviar antes das 12:00 do dia 2 (domingo)

---

## 8. Estrutura Sugerida do Repositório

```
docrag-br/
├── README.md              # visão do projeto + como rodar
├── requirements.txt
├── src/
│   ├── ingestion/
│   │   ├── text_chunker.py
│   │   ├── table_extractor.py
│   │   └── vision_processor.py
│   ├── embeddings/
│   │   └── embedder.py
│   ├── retrieval/
│   │   ├── router.py       # roteamento por intenção
│   │   └── reranker.py
│   ├── chat/
│   │   └── app.py          # interface (Streamlit)
│   └── config.py
├── data/
│   └── sample_docs/        # documentos de teste
└── demo/
    └── demo_video.mp4 (ou link)
```

---

## 9. Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| Tempo curto para sistema ambicioso | Escopo já cortado para MVP (seção 3) |
| Vision LLM lento/caro em muitas imagens | Limitar a poucos gráficos de exemplo na demo |
| Falta de time para revisar tudo | Buffer de 30min reservado antes do deadline |
| Demo não gravada a tempo | Gravar demo ANTES do polish final, não depois |

---

## 10. Links de Referência

- Página do evento: cerebralvalley.ai/e/raise-summit-hackathon/details
- Discord: discord.com/invite/N26eKqmR42
- Run of show: raise-hackathon-run-of-show.lovable.app
- Contato organização: @AJC no Discord

---

*Última atualização: 4 de julho de 2026, véspera do hackathon.*