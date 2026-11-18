import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader
from docx import Document as DocxDocument

from slai.llm.ollama_client import OllamaClient

from app.db import SessionLocal
from app.models import KnowledgeDocument, KnowledgeChunk

UPLOAD_DIR = Path("uploads")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

ollama = OllamaClient()


def get_qdrant():
    from qdrant_client import QdrantClient

    return QdrantClient(url=QDRANT_URL)


def collection_name(org_id: int) -> str:
    return f"knowledge_org_{org_id}"


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    if path.suffix.lower() == ".docx":
        document = DocxDocument(path)
        return "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

    raise ValueError("?????????????? ?????? PDF ? DOCX")


def split_text(text: str, size: int = 900) -> list[str]:
    text = " ".join(text.split())
    return [
        text[i:i + size]
        for i in range(0, len(text), size)
    ]


def save_upload(file: UploadFile) -> Path:
    UPLOAD_DIR.mkdir(exist_ok=True)

    file_id = uuid.uuid4().hex
    filename = Path(file.filename or "document").name
    path = UPLOAD_DIR / f"{file_id}_{filename}"

    with path.open("wb") as buffer:
        buffer.write(file.file.read())

    return path


def create_document(
    org_id: int,
    filename: str,
    path: Path,
) -> KnowledgeDocument:
    db = SessionLocal()

    try:
        document = KnowledgeDocument(
            org_id=org_id,
            filename=filename,
            status="processing",
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            text = extract_text(path)
            chunks = split_text(text)

            if not chunks:
                document.status = "error"
                document.error = "???????? ?? ???????? ???????????? ??????"
                db.commit()
                return document

            qdrant = get_qdrant()
            collection = collection_name(org_id)

            if not qdrant.collection_exists(collection):
                vector = ollama.embed("init", model=EMBEDDING_MODEL)
                qdrant.create_collection(
                    collection_name=collection,
                    vectors_config={
                        "knowledge": {
                            "size": len(vector),
                            "distance": "Cosine",
                        }
                    },
                )

            for index, chunk in enumerate(chunks):
                vector = ollama.embed(chunk, model=EMBEDDING_MODEL)

                qdrant.upsert(
                    collection_name=collection,
                    points=[
                        {
                            "id": document.id * 100000 + index,
                            "vector": {
                                "knowledge": vector,
                            },
                            "payload": {
                                "document_id": document.id,
                                "org_id": org_id,
                                "filename": filename,
                                "chunk_index": index,
                                "text": chunk,
                            },
                        }
                    ],
                )

                db.add(
                    KnowledgeChunk(
                        org_id=org_id,
                        document_id=document.id,
                        chunk_index=index,
                        text=chunk,
                    )
                )

            document.status = "ready"
            document.chunk_count = len(chunks)
            db.commit()
            db.refresh(document)

        except Exception as error:
            document.status = "error"
            document.error = str(error)
            db.commit()

        return document

    finally:
        db.close()


def search(
    org_id: int,
    question: str,
) -> tuple[str, list[dict]]:
    try:
        qdrant = get_qdrant()
        collection = collection_name(org_id)

        if not qdrant.collection_exists(collection):
            return "? ???? ?????? ???? ??? ??????????.", []

        vector = ollama.embed(question, model=EMBEDDING_MODEL)

        points = qdrant.query_points(
            collection_name=collection,
            query=vector,
            using="knowledge",
            with_payload=True,
            limit=5,
        ).points

        sources = [
            {
                "document_id": point.payload["document_id"],
                "filename": point.payload["filename"],
                "chunk_index": point.payload["chunk_index"],
                "text": point.payload["text"],
            }
            for point in points
        ]

        if not sources:
            return "?? ??????? ?????????? ? ?????????? ?????????.", []

        context = "\n\n".join(
            f"[{i + 1}] {source['text']}"
            for i, source in enumerate(sources)
        )

        prompt = (
            "?????? ?? ?????? ?????? ?? ?????? ?????????.\n"
            "?? ?????????? ?????.\n"
            "???? ?????? ??? ? ?????????, ??????: "
            "\"?? ??????? ?????????? ? ?????????? ?????????.\"\n"
            "?????? ?????? ?? ???????.\n\n"
            f"????????:\n{context}\n\n"
            f"??????: {question}"
        )

        answer = ollama.generate(prompt)

        return answer, sources

    except Exception:
        return "???? ?????? ???????? ??????????.", []
