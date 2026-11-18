import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer,
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_knowledge_documents_org_id",
        "knowledge_documents",
        ["org_id"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "org_id",
            sa.Integer,
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("knowledge_documents.id"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_knowledge_chunks_org_id",
        "knowledge_chunks",
        ["org_id"],
    )
    op.create_index(
        "ix_knowledge_chunks_document_id",
        "knowledge_chunks",
        ["document_id"],
    )


def downgrade():
    op.drop_index(
        "ix_knowledge_chunks_document_id",
        table_name="knowledge_chunks",
    )
    op.drop_index(
        "ix_knowledge_chunks_org_id",
        table_name="knowledge_chunks",
    )
    op.drop_table("knowledge_chunks")

    op.drop_index(
        "ix_knowledge_documents_org_id",
        table_name="knowledge_documents",
    )
    op.drop_table("knowledge_documents")
