"""Script de ingestao: processa todos os PDFs de data/sample_docs e indexa no Chroma.

Uso: python -m src.ingest [--skip-vision]
"""
import argparse
import sys

from src.config import SAMPLE_DOCS_DIR
from src.embeddings.embedder import index_chunks, reset_collection
from src.ingestion.table_extractor import extract_table_chunks
from src.ingestion.text_chunker import extract_text_chunks
from src.ingestion.vision_processor import extract_image_chunks


def ingest_pdf(pdf_path: str, skip_vision: bool = False) -> int:
    print(f"\n=== Ingerindo: {pdf_path} ===")

    text_chunks = extract_text_chunks(pdf_path)
    print(f"  Texto: {len(text_chunks)} chunks")

    table_chunks = extract_table_chunks(pdf_path)
    print(f"  Tabelas: {len(table_chunks)} chunks")

    image_chunks = []
    if skip_vision:
        print("  Graficos: pulado (--skip-vision)")
    else:
        image_chunks = extract_image_chunks(pdf_path)
        print(f"  Graficos/imagens: {len(image_chunks)} chunks")

    total = index_chunks(text_chunks + table_chunks + image_chunks)
    print(f"  Indexados: {total} chunks")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestao de PDFs no DocRAG BR")
    parser.add_argument(
        "--skip-vision",
        action="store_true",
        help="pula a descricao de graficos via Vision LLM (mais rapido, sem custo)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="apaga o indice antes de ingerir (use apos mudar o formato dos chunks)",
    )
    args = parser.parse_args()

    if args.reset:
        reset_collection()
        print("Indice apagado — reingestao do zero.")

    SAMPLE_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(SAMPLE_DOCS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF encontrado em {SAMPLE_DOCS_DIR}. Adicione documentos e rode de novo.")
        sys.exit(1)

    total = sum(ingest_pdf(str(pdf), skip_vision=args.skip_vision) for pdf in pdfs)
    print(f"\nConcluido: {total} chunks indexados de {len(pdfs)} documento(s).")


if __name__ == "__main__":
    main()
