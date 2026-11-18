from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select

from app.db import get_db
from app.models import KnowledgeDocument
from app.security import require
from app.knowledge.schemas import (
    KnowledgeDocumentOut,
    KnowledgeSearchIn,
    KnowledgeSearchOut,
)
from app.knowledge.service import (
    create_document,
    save_upload,
    search,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post("/documents", status_code=201)
def upload_document(
    file: UploadFile = File(...),
    p=Depends(require("knowledge:write")),
    db=Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "Файл не выбран")

    if not file.filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(
            400,
            "Поддерживаются только PDF и DOCX",
        )

    path = save_upload(file)

    document = create_document(
        org_id=p.org_id,
        filename=file.filename,
        path=path,
    )

    return KnowledgeDocumentOut(
        id=document.id,
        filename=document.filename,
        status=document.status,
        chunk_count=document.chunk_count,
        error=document.error,
    )


@router.get("/documents")
def list_documents(
    p=Depends(require("knowledge:read")),
    db=Depends(get_db),
):
    rows = db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.org_id == p.org_id)
        .order_by(KnowledgeDocument.id.desc())
    ).all()

    return [
        KnowledgeDocumentOut(
            id=row.id,
            filename=row.filename,
            status=row.status,
            chunk_count=row.chunk_count,
            error=row.error,
        )
        for row in rows
    ]


@router.post("/search")
def search_knowledge(
    body: KnowledgeSearchIn,
    p=Depends(require("knowledge:read")),
):
    answer, sources = search(
        org_id=p.org_id,
        question=body.question,
    )

    return KnowledgeSearchOut(
        answer=answer,
        sources=[
            KnowledgeSourceOut(**source)
            for source in sources
        ],
    )
