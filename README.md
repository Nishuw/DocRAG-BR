# DocRAG BR 🔎

**O analista autônomo que audita o documento — e prova cada afirmação até o pixel.**

LLMs inventam números — e em finanças, número inventado é passivo jurídico. Todo mundo construiu "chat com PDF": máquinas de responder perguntas. O DocRAG BR inverte o fluxo — aqui, **o sistema fala primeiro**:

1. **🕵️ Lê o documento antes de você** — sem nenhuma pergunta, o auditor autônomo cruza o que o **texto narrativo afirma** com o que as **tabelas e gráficos mostram**, e entrega descobertas: inconsistências, variações que o texto minimiza, afirmações sem sustentação numérica. Só chega ao usuário a descoberta cujos números foram **comprovados na fonte**.
2. **✅ Audita cada número automaticamente** — todo valor (de resposta ou descoberta) é procurado no documento original; o que não for encontrado ganha um ⚠️ na frente do usuário, com a taxa de fidelidade. **O sistema flagra a própria alucinação em tempo real.**
3. **📄 Aponta para o pixel** — cada citação abre a página real do PDF com o trecho citado **destacado em amarelo**. Não confie: verifique.
4. **📊 Enxerga gráficos vetoriais** — gráficos de relatórios modernos são desenhos vetoriais, invisíveis para pipelines comuns de extração de imagem. Aqui, páginas com gráficos são detectadas e renderizadas por inteiro para um Vision LLM.

> Projeto desenvolvido para o **RAISE Summit Hackathon** (4-5 de julho de 2026) por Ryan Nishikawa. Todos os LLMs via **OpenRouter**.

## O problema

Empresas brasileiras perdem tempo e dinheiro extraindo manualmente informação de documentos densos (relatórios trimestrais, balanços, documentos CVM). Ferramentas de RAG genéricas têm dois defeitos fatais para o setor financeiro:

- **Só lidam bem com texto corrido** — tabelas e gráficos (onde os números moram) ficam de fora.
- **Pedem confiança cega** — a "citação" é texto que o LLM escreve, sem nenhuma garantia de que o número citado existe na fonte.

O DocRAG BR ataca os dois: ingestão dedicada por tipo de conteúdo + **camada de verificação pós-resposta** que transforma a citação de promessa em prova.

## Como funciona

```
Documento (PDF)
      │
      ▼
┌──────────────────────────────────────────┐
│         INGESTÃO MULTI-FORMATO            │
│  Texto   → chunking por sentença          │
│  Tabela  → pdfplumber → markdown + título │
│  Gráfico → detecção de páginas com        │
│            vetores → render → Vision LLM  │
└──────────────────────────────────────────┘
      │
      ▼
Embeddings (sentence-transformers, multilíngue, local)
      │
      ▼
Vector store (ChromaDB, persistente)
      │
      ▼
┌──────────────────────────────────────────┐
│       RETRIEVAL EM 2 ESTÁGIOS             │
│  1. Roteamento por intenção (LLM)         │
│  2. Reranking dos top chunks (LLM)        │
└──────────────────────────────────────────┘
      │
      ▼
Resposta em streaming + citação [arquivo, pag. X]
      │
      ▼
┌──────────────────────────────────────────┐
│       CAMADA DE VERIFICAÇÃO               │
│  ✅ Auditoria numérica: cada valor da     │
│     resposta é conferido contra a fonte   │
│  📄 Grounding visual: citação → página    │
│     real com o trecho destacado           │
└──────────────────────────────────────────┘
      │
      ▼
CLI rica no terminal (python -m src.cli)

┌──────────────────────────────────────────┐
│   🕵️ AUDITORIA AUTÔNOMA (sem pergunta)    │
│  O sistema interroga o documento:         │
│  texto narrativo × tabelas × gráficos     │
│  → descobertas com números comprovados    │
│    na fonte e trecho destacado na página  │
└──────────────────────────────────────────┘
```

## Stack

| Camada | Tecnologia |
|---|---|
| Extração de PDF + render de páginas | PyMuPDF (fitz) |
| Extração de tabelas (com título/legenda) | pdfplumber |
| Vision LLM (páginas com gráficos) | OpenRouter (`google/gemini-2.5-flash`) |
| Embeddings | `sentence-transformers` (multilíngue, local, sem custo) |
| Vector store | ChromaDB |
| Roteamento + reranking | LLM via OpenRouter |
| Resposta final (streaming) | LLM via OpenRouter |
| Auditoria numérica | Regex BR + matching contra chunks-fonte (local, determinístico) |
| Interface | **CLI rica (terminal-first, estilo Claude Code)** — Rich/TUI |

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
#   --skip-vision  pula os gráficos (rápido, sem custo)
#   --reset        apaga o índice antes de ingerir

# 5. Abrir o cockpit no terminal
python -m src.cli
```

Dentro da CLI: pergunte em linguagem natural, ou use a paleta de comandos —
`/audit` (auditoria autônoma), `/find` (busca semântica local), `/open N`
(abre a página real do PDF com o trecho destacado), `/lang en|pt`, `/stats`
(tokens e custo estimado da sessão), `/help`.

## Estrutura do repositório

```
docrag-br/
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py               # configuração central
│   ├── ingest.py               # script de ingestão (python -m src.ingest)
│   ├── rag.py                  # pipeline de consulta + resposta em streaming
│   ├── ingestion/
│   │   ├── text_chunker.py     # texto → chunks por sentença
│   │   ├── table_extractor.py  # tabelas → markdown com título/legenda
│   │   └── vision_processor.py # páginas com gráficos → Vision LLM
│   ├── embeddings/
│   │   └── embedder.py         # embeddings + ChromaDB
│   ├── retrieval/
│   │   ├── router.py           # estágio 1: roteamento por intenção
│   │   └── reranker.py         # estágio 2: reranking via LLM
│   ├── verification/
│   │   ├── verifier.py         # auditoria numérica da resposta
│   │   └── auditor.py          # auditoria autônoma: descobertas sem pergunta
│   ├── cli.py                  # interface principal: cockpit no terminal
│   └── chat/
│       └── pdf_preview.py      # grounding visual (página + highlight)
├── data/
│   └── sample_docs/            # documentos de teste (B3/CVM)
└── demo/
    └── demo_video.mp4          # vídeo demo de 1 minuto
```

## Por que a auditoria numérica importa

O prompt de resposta exige reproduzir valores exatamente como na fonte — mas prompt é pedido, não garantia. A camada de verificação fecha o ciclo: extrai cada número da resposta (tolerante a formatos BR: `R$ 61.412`, `4,2%`, `61,4`), normaliza e procura nos chunks usados como fonte. O resultado aparece na interface como ✅ (confirmado no documento) ou ⚠️ (não localizado — confira antes de usar), com a taxa de fidelidade da resposta. **O sistema pega a própria alucinação em tempo real.**

## Visão: prova, não promessa

A auditoria autônoma é o primeiro estágio de uma tese maior — **IA auditável**: o sistema nunca afirma o que não pode provar. Os próximos estágios reutilizam o mesmo motor de verificação:

- **Cálculo auditado** — perguntas como "quanto variou a margem?" não são calculadas pelo LLM: ele emite a fórmula e os operandos, cada operando é verificado contra a fonte e a aritmética roda em código, determinística. A resposta exibe a prova: `margem 1T26 (✅ pág. 4) − margem 1T25 (✅ pág. 4) = −2,1 p.p.`
- **Gêmeo temporal da empresa** — cada trimestre ingerido vira um ponto na série; o sistema rastreia o que a diretoria **prometeu vs. o que entregou** entre filings.
- **Memorando de compliance** — o briefing auditado exportado como relatório assinado com a taxa de fidelidade e as páginas-fonte.
- Monitoramento contínuo de novos filings CVM com alertas; índice híbrido (denso + BM25); comparação multi-documento em escala (carteiras inteiras da B3).
