"""
Knowledge base ingestion pipeline with hierarchical section parsing and rich metadata extraction.

Extracts:
- source (filename)
- document_type (guide, architecture, standards, policy, overview, faq, org_structure)
- category (Environment Setup, Architecture, Engineering Standards, Policies, FAQ, etc.)
- role (backend, frontend, devops, all)
- experience_level (intern, junior, senior, all)
- technology (Node.js, Python, React, Kubernetes/AWS, General)
- section / title
"""
import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.rag.vectorstore import get_vectorstore

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
KB_PATH = BASE_DIR / "knowledge_base"


def _determine_doc_type(filename: str) -> str:
    fn = filename.lower()
    if "setup" in fn or "guide" in fn:
        return "guide"
    if "architecture" in fn:
        return "architecture"
    if "standards" in fn or "spec" in fn:
        return "standards"
    if "policy" in fn or "policies" in fn:
        return "policy"
    if "overview" in fn or "company" in fn:
        return "overview"
    if "faq" in fn:
        return "faq"
    if "org" in fn or "structure" in fn:
        return "org_structure"
    return "documentation"


def _extract_section_metadata(
    filename: str,
    h1: str,
    h2: str,
    h3: str,
    text: str,
) -> Dict[str, Any]:
    """
    Extract reliable metadata from document section hierarchy and text content.
    Combines parent guide/topic and sub-step headers for accurate context.
    """
    doc_type = _determine_doc_type(filename)
    context_str = f"{h1} {h2} {h3} {text[:300]}".lower()

    # Defaults
    role = "all"
    experience_level = "all"
    technology = "General"
    category = "Documentation"

    if doc_type == "overview":
        category = "Company Overview"
    elif doc_type == "policy":
        category = "Policies & Security"
    elif doc_type == "org_structure":
        category = "Organization Structure"
    elif doc_type == "faq":
        category = "FAQ"
    elif doc_type == "standards":
        category = "Engineering Standards"
    elif doc_type == "architecture":
        category = "Architecture"
    elif doc_type == "guide":
        category = "Environment Setup"

    # Targeted Role & Technology inference from full section hierarchy
    if any(k in context_str for k in ["guide 1: node.js", "node.js backend", "connector-runtime", "gateway-service", "auth-service", "express", "notification-service", "pnpm"]):
        role = "backend"
        technology = "Node.js"
        if "setup" in context_str or "guide" in context_str:
            category = "Environment Setup"
    elif any(k in context_str for k in ["guide 2: python", "python backend", "workflow-core", "workflow-executor", "django", "poetry", "alembic", "uvicorn", "fastapi"]):
        role = "backend"
        technology = "Python"
        if "setup" in context_str or "guide" in context_str:
            category = "Environment Setup"
    elif any(k in context_str for k in ["guide 3: frontend", "frontend setup", "flowengine-web", "react", "storybook", "zustand", "ui-kit", "tailwind"]):
        role = "frontend"
        technology = "React"
        if "setup" in context_str or "guide" in context_str:
            category = "Environment Setup"
    elif any(k in context_str for k in ["guide 4: devops", "devops / platform", "infrastructure & cloud", "terraform", "kubernetes", "eks", "helm", "aws", "argocd", "datadog", "wireguard", "k9s"]):
        role = "devops"
        technology = "Kubernetes/AWS"
        if "setup" in context_str or "guide" in context_str:
            category = "Cloud Infrastructure"

    # Experience level inference (when specific)
    if "intern" in context_str:
        experience_level = "intern"
    elif "senior" in context_str or any(k in context_str for k in ["sla", "on-call rotation", "sprint planning", "stakeholder sync"]):
        experience_level = "senior"
    elif "junior" in context_str:
        experience_level = "junior"

    section_display = h2 if h2 else h1
    if h3 and h3 != h2:
        section_display = f"{h2} > {h3}" if h2 else h3

    return {
        "source": filename,
        "document_type": doc_type,
        "category": category,
        "role": role,
        "experience_level": experience_level,
        "technology": technology,
        "section": section_display or "General",
        "title": section_display or filename,
    }


def parse_and_split_markdown_file(file_path: Path) -> List[Document]:
    """Parse markdown file preserving hierarchical H1/H2/H3 headers for all chunks."""
    content = file_path.read_text(encoding="utf-8")
    filename = file_path.name

    lines = content.splitlines()
    current_h1 = file_path.stem.replace("_", " ").title()
    current_h2 = ""
    current_h3 = ""
    current_block: List[str] = []
    sections: List[tuple[str, str, str, str]] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            if current_block:
                sections.append((current_h1, current_h2, current_h3, "\n".join(current_block)))
                current_block = []
            current_h1 = re.sub(r"^#\s+", "", stripped).strip()
            current_h2 = ""
            current_h3 = ""
        elif stripped.startswith("## "):
            if current_block:
                sections.append((current_h1, current_h2, current_h3, "\n".join(current_block)))
                current_block = []
            current_h2 = re.sub(r"^##\s+", "", stripped).strip()
            current_h3 = ""
        elif stripped.startswith("### "):
            if current_block:
                sections.append((current_h1, current_h2, current_h3, "\n".join(current_block)))
                current_block = []
            current_h3 = re.sub(r"^###\s+", "", stripped).strip()
        else:
            current_block.append(line)

    if current_block:
        sections.append((current_h1, current_h2, current_h3, "\n".join(current_block)))

    documents_to_chunk: List[Document] = []
    for h1, h2, h3, body in sections:
        if not body.strip():
            continue
        meta = _extract_section_metadata(filename, h1, h2, h3, body)
        header_text = f"## {h2}\n### {h3}\n\n" if h2 and h3 else (f"## {h2}\n\n" if h2 else f"# {h1}\n\n")
        full_text = f"{header_text}{body}"
        documents_to_chunk.append(Document(page_content=full_text, metadata=meta))

    # Split larger sections into manageable chunks while preserving metadata
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""],
    )

    final_chunks: List[Document] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for doc in documents_to_chunk:
        split_docs = splitter.split_documents([doc])
        for chunk in split_docs:
            chunk.metadata["ingested_at"] = now_iso
            final_chunks.append(chunk)

    return final_chunks


def load_and_chunk_knowledge_base() -> List[Document]:
    """Load all markdown documents from knowledge_base directory and generate enriched chunks."""
    all_chunks: List[Document] = []
    for file_path in sorted(KB_PATH.glob("**/*.md")):
        if file_path.is_file() and file_path.stat().st_size > 0:
            chunks = parse_and_split_markdown_file(file_path)
            all_chunks.extend(chunks)
    return all_chunks


def remove_document_chunks(filename: str) -> int:
    """Delete every stored chunk that came from one knowledge base file. Returns the count removed."""
    vectorstore = get_vectorstore()
    ids = vectorstore.get(where={"source": filename}).get("ids", [])
    if ids:
        vectorstore.delete(ids=ids)
    return len(ids)


def reindex_document(file_path: Path) -> int:
    """Replace one file's chunks in the vector store so edits are searchable immediately."""
    remove_document_chunks(file_path.name)
    chunks = parse_and_split_markdown_file(file_path)
    if chunks:
        get_vectorstore().add_documents(chunks)
    return len(chunks)


def ingest_knowledge_base():
    """Ingest knowledge base documents into ChromaDB with enriched metadata."""
    print("Loading and chunking knowledge base documents...")
    chunks = load_and_chunk_knowledge_base()
    print(f"Generated {len(chunks)} enriched document chunks.")

    vectorstore = get_vectorstore()
    print("Storing embeddings in ChromaDB...")
    vectorstore.add_documents(chunks)

    persist = getattr(vectorstore, "persist", None)
    if callable(persist):
        persist()

    logger.info("Knowledge base ingestion complete.")


if __name__ == "__main__":
    ingest_knowledge_base()