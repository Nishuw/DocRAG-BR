"""Configuracao central do DocRAG BR."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
SAMPLE_DOCS_DIR = DATA_DIR / "sample_docs"
CHROMA_DIR = DATA_DIR / "chroma"

# OpenRouter (camada unica de acesso a todos os LLMs — qualifica bonus track)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Modelos via OpenRouter
VISION_MODEL = os.getenv("VISION_MODEL", "google/gemini-2.5-flash")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")

# Embeddings locais (sem custo, multilingue — funciona bem em portugues)
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)

COLLECTION_NAME = "docrag_br"

# Chunking
MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP_SENTENCES = 1

# Retrieval
TOP_K_RETRIEVAL = 12   # candidatos do estagio 1
TOP_K_FINAL = 4        # apos reranking

# Vision: paginas inteiras renderizadas para o Vision LLM.
# Graficos de relatorios financeiros costumam ser desenhos VETORIAIS (nao
# imagens embutidas), entao a unidade de processamento e a pagina renderizada.
MAX_VISION_PAGES_PER_DOC = 10   # limite de paginas por documento (custo/tempo)
MIN_IMAGE_SIZE_PX = 120         # imagem raster menor que isso nao conta como grafico
MIN_CHART_PALETTE_COLORS = 4    # cores de preenchimento distintas para a pagina ser candidata
VISION_PAGE_DPI = 150           # resolucao do render enviado ao Vision LLM
