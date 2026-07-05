# DocRAG BR — Registro de Implementação

**Data:** 5 de julho de 2026 (Dia 2 — manhã do deadline)
**Status geral:** Produto completo com chave ativa: ingestão (texto+tabelas+**gráficos reais**) → retrieval → chat com streaming + verificação + **auditoria autônoma** (o sistema fala primeiro). Falta: gravar demo e submeter até 12:00.

---

## -2. Rodada 4 (Dia 2, ~11h) — pivô de interface: terminal-first

Streamlit **removido do produto** (preservado no histórico git, commit `f72f4a6`). Interface principal agora é uma **CLI rica** (`python -m src.cli`, Rich): cockpit de auditoria estilo Claude Code — header de plataforma, respostas em streaming com números marcados ✓/⚠ inline, barra de fidelidade, painéis de descobertas com cor por severidade, `/find` (explorador semântico local), `/open N` (abre a página real com highlight no visualizador do SO), `/lang en|pt`, `/stats` (tokens + custo estimado). Web UI virou proposta de arquitetura em `UX-DESIGN.md` (companion de visualização: Next.js + FastAPI + WebSockets). Racional: para jurados técnicos, terminal-first comunica plataforma, não chatbot.

---

## -1. Rodada 3 (Dia 2, manhã) — "o analista autônomo que fala primeiro"

Reposicionamento final: de "o RAG que audita a própria resposta" para **"o analista autônomo que audita o documento — e prova cada afirmação até o pixel"**.

| Item | Detalhe |
|---|---|
| ✅ **Auditoria autônoma** (`src/verification/auditor.py`) | Sem nenhuma pergunta, o sistema cruza texto narrativo × tabelas × gráficos e gera 3-5 descobertas (inconsistências, variações minimizadas, afirmações sem sustentação). Cada descoberta passa pelo verificador; descoberta sem nenhum número comprovado é descartada. Botão "🕵️ Auditar documento" na UI + cards com selos ✅/⚠️ e página destacada. Teste real: 5 descobertas, incl. FCO em US$ no texto vs R$ na tabela, e um número derivado pelo LLM flagrado com ⚠️. |
| ✅ **Visão consertada de verdade** (`vision_processor.py`) | O ranking por densidade de desenhos selecionava páginas de TABELA (centenas de traços) e o Vision LLM respondia IRRELEVANTE para todas. Novo seletor: paleta de cores de preenchimento distintas (gráficos usam várias; tabelas 1-2) com desempate contra excesso de desenhos. Resultado: pág. 4 (EBITDA/Lucro/FCO) e pág. 8 (waterfall CAPEX) indexadas. |
| ✅ **Retrieval honra o roteamento** (`rag.py`) | O reranker descartava os chunks de gráfico mesmo com a pergunta roteada para GRÁFICO. Agora, se o usuário pediu gráfico/tabela, os 2 melhores chunks do tipo são garantidos no resultado. Teste: "o que mostra o gráfico de FCO?" → resposta com 5/5 números confirmados, lidos do gráfico vetorial. |
| ✅ **`max_tokens` explícito em toda chamada** | Sem ele, a OpenRouter assume o máximo do modelo (65k) e contas com pouco crédito recebem 402 antes de gerar. Corrigido em visão (4000), resposta (3000) e auditor (4000). |
| ✅ **README reposicionado** | Novo pitch, auditoria autônoma como feature nº 1, visão "prova, não promessa" (cálculo auditado, gêmeo temporal, memorando de compliance). |

**Atenção:** saldo da OpenRouter está em centavos — adicionar ~US$5 antes de gravar a demo para não morrer no meio.

---

## 0. Rodada 2 (Dia 1, tarde) — reposicionamento "o RAG que prova o que diz"

O pitch mudou de "RAG com citação" para **"o assistente que audita a própria resposta"**. O que foi feito:

| Item | Detalhe |
|---|---|
| ✅ **Auditoria numérica** (`src/verification/verifier.py`) | Todo número da resposta (formatos BR: `R$ 61.412`, `4,2%`, `61,4`) é procurado nos chunks-fonte. UI mostra ✅/⚠️ por número + taxa de fidelidade. Ignora trimestres (`1T26`), citações de página e inteiros soltos. Testado com 5 casos (inclui alucinação detectada). |
| ✅ **Grounding visual** (`src/chat/pdf_preview.py`) | Cada fonte na UI tem aba "Página original": página real do PDF renderizada com o trecho citado **destacado em amarelo** (PyMuPDF `search_for` + `add_highlight_annot`). Testado na pág. 4 da Petrobras. |
| ✅ **Correção crítica da visão** (`vision_processor.py`) | O método antigo (`page.get_images`) via só **5 imagens raster** no PDF inteiro (capa/contracapa!) — todos os gráficos são **vetoriais** e eram ignorados. Agora: páginas candidatas detectadas por densidade de desenhos vetoriais + raster, renderizadas por inteiro (150 dpi) para o Vision LLM. 10 páginas selecionadas no doc da Petrobras (antes: nenhuma com gráfico real). |
| ✅ **Bug crítico de dependência** | `openai 1.54.4` + `httpx 0.28.1` = **toda chamada de LLM quebrava** (`unexpected keyword argument 'proxies'`) mesmo com chave válida — mascarado pelos fallbacks silenciosos. Corrigido: `openai==2.44.0` (requirements atualizado e instalado). |
| ✅ **Streaming** (`rag.py: answer_stream`) | Resposta chega token a token na UI (`st.write_stream`); ao final, o texto é substituído pela versão anotada com ✅/⚠️. |
| ✅ **Tabelas com título/legenda** (`table_extractor.py`) | Cada tabela agora é prefixada com o texto logo acima dela na página (ex: "TABELA 1 – PRINCIPAIS INDICADORES") — antes era só grade de números sem semântica. |
| ✅ **Perguntas sugeridas** (`app.py`) | 4 botões clicáveis na primeira visita, calibrados para o doc da Petrobras. |
| ✅ **Prompt comparativo** (`rag.py`) | Perguntas comparando documentos/períodos geram tabela markdown; regra reforçada de nunca arredondar (alimenta a auditoria). |
| ✅ **`--reset` na ingestão** | `python -m src.ingest --reset` apaga o índice antes (necessário quando o formato dos chunks muda). Reingestão executada: 112 chunks limpos. |

**Testes da rodada 2 (todos passaram):** verificador (5 casos, incl. alucinação flagrada), render com highlight na página real, scoring de páginas com gráfico no PDF real, retrieval ponta a ponta sem chave (fallbacks OK, agora com 401 em vez de crash), reingestão limpa, app sobe com HTTP 200.

---

## 1. O que foi construído

### Estrutura do repositório

```
DocRAG BR/
├── README.md               # visão do projeto + como rodar
├── PROGRESS.md             # este documento
├── Project Guide.md        # guia mestre original
├── requirements.txt        # dependências (Python 3.11)
├── .env.example            # template de configuração
├── .env                    # criado — FALTA preencher OPENROUTER_API_KEY
├── .gitignore
├── src/
│   ├── config.py           # configuração central
│   ├── ingest.py           # script de ingestão (python -m src.ingest)
│   ├── rag.py              # pipeline de consulta + resposta com citação
│   ├── ingestion/
│   │   ├── text_chunker.py
│   │   ├── table_extractor.py
│   │   └── vision_processor.py
│   ├── embeddings/
│   │   └── embedder.py
│   ├── retrieval/
│   │   ├── router.py
│   │   └── reranker.py
│   └── chat/
│       └── app.py          # interface Streamlit
├── data/
│   ├── sample_docs/
│   │   └── petrobras_desempenho_1T26.pdf   # documento de teste real
│   └── chroma/             # vector store persistente (gerado na ingestão)
└── demo/                   # reservado para o vídeo de 1 min
```

### Ingestão multi-formato (`src/ingestion/`)

| Módulo | O que faz |
|---|---|
| `text_chunker.py` | Extrai texto por página com PyMuPDF, divide em sentenças (com tratamento de abreviações BR como "S.A.", "Ltda") e agrupa em chunks de até 1.200 caracteres com overlap de 1 sentença. |
| `table_extractor.py` | Extrai tabelas com pdfplumber e serializa cada uma como markdown, prefixada com número da tabela e página. |
| `vision_processor.py` | Extrai imagens do PDF e envia ao Vision LLM (OpenRouter, `google/gemini-2.5-flash`) com prompt que exige descrição exaustiva dos dados. Filtra ícones/logos (mínimo 120px, resposta "IRRELEVANTE") e limita a 10 imagens por documento para controlar custo/tempo. |

Todo chunk carrega metadados de fonte: arquivo, página e tipo (`text` / `table` / `image`).

### Embeddings + vector store (`src/embeddings/embedder.py`)

- Embeddings locais com `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`) — multilíngue, funciona bem em português e não custa nada.
- ChromaDB persistente em `data/chroma/`, distância cosseno.
- Ingestão idempotente: IDs por hash SHA-1 de (fonte + página + conteúdo), então rodar de novo não duplica.

### Retrieval em 2 estágios (`src/retrieval/` + `src/rag.py`)

1. **Roteamento por intenção** (`router.py`): LLM classifica a pergunta em TABELA / GRÁFICO / TEXTO / GERAL e a busca prioriza o tipo de chunk correspondente. Se o filtro retornar poucos resultados, complementa com busca geral.
2. **Reranking** (`reranker.py`): LLM reordena os 12 candidatos da busca densa e devolve os 4 melhores.

Ambos os estágios têm fallback: se a chamada de LLM falhar, a ordem da busca densa é mantida — a busca nunca quebra.

### Resposta com citação obrigatória (`src/rag.py`)

O prompt de resposta exige: citar fonte no formato `[arquivo, pag. X]` em toda afirmação, nunca inventar, reproduzir valores exatamente como na fonte, responder em português.

### Interface de chat (`src/chat/app.py`)

Streamlit com histórico de conversa, expansores mostrando os chunks-fonte de cada resposta (arquivo, página, tipo) e sidebar com contagem de chunks indexados.

### Configuração (`src/config.py`)

Tudo via OpenRouter (qualifica o bônus track): visão, roteamento, reranking e resposta final usam `google/gemini-2.5-flash` (sobrescrevível via `.env`). Parâmetros de chunking e retrieval centralizados.

---

## 2. Testes executados (todos passaram)

1. **Instalação**: `pip install -r requirements.txt` concluída sem erros (Python 3.11.9).
2. **Ingestão sem visão** (`python -m src.ingest --skip-vision`): 112 chunks indexados do PDF da Petrobras — 75 de texto + 37 de tabelas.
3. **Busca densa**: perguntas sobre lucro líquido, EBITDA ajustado e dívida bruta retornaram os trechos/páginas corretos do relatório.
4. **Interface**: Streamlit sobe e responde em http://localhost:8501.

---

## 3. Dados de teste

**Documento:** Relatório de Desempenho Financeiro 1T26 da Petrobras (1,4 MB, baixado em `data/sample_docs/petrobras_desempenho_1T26.pdf`). Contém texto denso, dezenas de tabelas e gráficos — ideal para demonstrar os três formatos de ingestão.

---

## 4. Pendências (ação sua)

1. **Preencher `OPENROUTER_API_KEY` no `.env`** (pegar em https://openrouter.ai/keys). Sem ela: busca funciona, mas resposta final, roteamento, reranking e visão não.
2. Com a chave, rodar a **ingestão completa com visão**: `python -m src.ingest --reset` (o `--reset` garante índice limpo com os novos chunks de gráficos).
3. Testar o chat de ponta a ponta — conferir os ✅ acendendo e a página destacada nas fontes.
4. **Baixar um 2º documento** (ex: Vale 1T26 ou Petrobras 1T25) para `data/sample_docs/` e reingerir — habilita as perguntas comparativas com tabela.
5. (Dia 2) Gravar demo de 1 min. **Roteiro sugerido**: pergunta normal (✅ acendendo) → clique na fonte (página com highlight) → **pergunta plantada que gera um ⚠️** ("o sistema pega a própria alucinação ao vivo") → pergunta comparativa. Gravar ANTES do polish final.
6. Revisar checklist de submissão (seção 7 do Project Guide) e marcar bônus track OpenRouter.

---

## 5. Observações do ambiente

- O `python` do PATH desta máquina aponta para um venv de terceiros (`hermes-agent`). Use o Python direto: `C:\Users\ryanj\AppData\Local\Programs\Python\Python311\python.exe`.
- No terminal Windows, se aparecer `UnicodeEncodeError`, rode antes: `$env:PYTHONIOENCODING="utf-8"`.

### Comandos úteis

```powershell
$py = "C:\Users\ryanj\AppData\Local\Programs\Python\Python311\python.exe"

# Ingestão completa (com visão)
& $py -m src.ingest

# Ingestão rápida (sem visão, sem custo)
& $py -m src.ingest --skip-vision

# Chat
& $py -m streamlit run src/chat/app.py
```
