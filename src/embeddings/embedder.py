"""Embeddings locais (sentence-transformers) + vector store Chroma."""
import hashlib
from functools import lru_cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def reset_collection() -> None:
    """Apaga a colecao (usado por `python -m src.ingest --reset`)."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:  # noqa: BLE001 — colecao pode nao existir ainda
        pass
    get_collection.cache_clear()


def _chunk_id(chunk: dict) -> str:
    raw = f"{chunk['source']}|{chunk['page']}|{chunk['content']}"
    return hashlib.sha1(raw.encode()).hexdigest()


def index_chunks(chunks: list[dict], batch_size: int = 64) -> int:
    """Gera embeddings e insere no Chroma. Idempotente (ids por hash)."""
    if not chunks:
        return 0
    collection = get_collection()
    model = get_model()
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["content"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        collection.upsert(
            ids=[_chunk_id(c) for c in batch],
            documents=texts,
            embeddings=embeddings,
            metadatas=[
                {
                    "type": c["type"],
                    "source": Path(c["source"]).name,
                    "page": c["page"],
                }
                for c in batch
            ],
        )
    return len(chunks)


def query_chunks(query: str, top_k: int, content_type: str | None = None) -> list[dict]:
    """Busca densa no Chroma. Filtra por tipo de conteudo se informado."""
    collection = get_collection()
    embedding = get_model().encode([query]).tolist()
    where = {"type": content_type} if content_type else None
    res = collection.query(
        query_embeddings=embedding,
        n_results=min(top_k, max(collection.count(), 1)),
        where=where,
    )
    results = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        results.append(
            {
                "content": doc,
                "type": meta["type"],
                "source": meta["source"],
                "page": meta["page"],
                "distance": dist,
            }
        )
    return results
