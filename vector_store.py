"""
Vector Store Manager — Embeds FAQ questions and stores them in ChromaDB.

Handles:
- Question-only embedding using sentence-transformers
- ChromaDB collection management (create, upsert, query)
- Metadata storage for verbatim answer retrieval
"""

import os
import json
import chromadb
from chromadb.utils import embedding_functions
from models import QAPair


# Default model — good balance of speed and quality
DEFAULT_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "pharma_faq"
DB_PATH = os.path.join(os.path.dirname(__file__), "vector_db")


class FAQVectorStore:
    """Manages embedding and storage of FAQ Q-A pairs in ChromaDB."""

    def __init__(self, db_path: str = DB_PATH, model_name: str = DEFAULT_MODEL):
        self.db_path = db_path
        self.model_name = model_name

        # Initialize ChromaDB persistent client
        self.client = chromadb.PersistentClient(path=db_path)

        # Initialize embedding function (same model for ingestion + query)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )

        # Get or create the collection
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"}  # cosine similarity
        )
        print(f"  ✅ ChromaDB collection '{COLLECTION_NAME}' ready "
              f"({self.collection.count()} existing documents)")

    def ingest(self, qa_pairs: list[QAPair]) -> int:
        """
        Ingest Q-A pairs into the vector store.

        - Embeds ONLY the question text
        - Stores the verbatim answer + metadata for later retrieval

        Returns:
            Number of pairs ingested.
        """
        if not qa_pairs:
            return 0

        ids = []
        documents = []  # question text only — this gets embedded
        metadatas = []

        for qa in qa_pairs:
            ids.append(qa.faq_id)

            # IMPORTANT: The Question theme is identical across all blocks in the DOCX!
            # To ensure different topics (Missed Dose, Hepatic Impairment) don't collide in semantic space,
            # we composite the underlying Anchor topic directly into the embedding vector.
            clean_anchor = qa.section.replace("_", " ").title()
            composite_embedding_text = f"Topic: {clean_anchor} | Question: {qa.question}"
            documents.append(composite_embedding_text)

            # Store enriched metadata for filtering and hybrid search
            metadata = {
                "source_doc": qa.source_doc,
                "product": qa.product,
                "audience": qa.audience,
                "clinical_terms": qa.clinical_terms
            }
            metadatas.append(metadata)

        # Upsert into ChromaDB (handles duplicates by FAQ ID)
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        print(f"  ✅ Ingested {len(ids)} Q-A pairs into vector store")
        return len(ids)

    def get_stats(self) -> dict:
        """Return stats about the current collection."""
        count = self.collection.count()

        # Get unique source docs
        if count > 0:
            all_meta = self.collection.get(include=["metadatas"])
            source_docs = set(m.get("source_doc", "") for m in all_meta["metadatas"])
        else:
            source_docs = set()

        return {
            "total_qa_pairs": count,
            "source_documents": len(source_docs),
            "source_doc_names": sorted(source_docs),

            "embedding_model": self.model_name,
            "db_path": self.db_path,
        }

    def reset(self):
        """Delete and recreate the collection."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"  🗑️  Collection '{COLLECTION_NAME}' reset")
