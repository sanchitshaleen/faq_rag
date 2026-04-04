# Workaround for ChromaDB SQLite version on Hugging Face Spaces
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import json
from dataclasses import dataclass
from typing import Optional, List, Dict
from vector_store import FAQVectorStore
from database import FAQDatabase
from sentence_transformers import CrossEncoder


# Model for reranking - lightweight but effective
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


# Confidence thresholds (cosine distance: lower = more similar)
# ChromaDB returns distances, not similarities for cosine.
# cosine_distance = 1 - cosine_similarity
# So: distance < 0.3  → similarity > 0.7 (high confidence)
#     distance 0.3-0.6 → similarity 0.4-0.7 (medium confidence)
#     distance > 0.6   → similarity < 0.4 (low confidence)
HIGH_CONFIDENCE_THRESHOLD = 0.24
MEDIUM_CONFIDENCE_THRESHOLD = 0.50

# Hybrid Search Weights (must sum to 1.0)
HYBRID_SEMANTIC_WEIGHT = 0.7
HYBRID_KEYWORD_WEIGHT = 0.3


@dataclass
class RetrievalResult:
    """Result from a FAQ retrieval query."""
    faq_id: str
    matched_question: str
    answer_text: str
    answer_table_html: Optional[str]
    answer_table_text: Optional[str]
    source_doc: str
    page_num: int
    section: str
    distance: float  # cosine distance (lower = better)
    confidence: str  # "high", "medium", "low"
    channels: dict   # Nested channel responses

    @property
    def similarity_score(self) -> float:
        """Convert cosine distance to similarity score (0-1)."""
        return round(1 - self.distance, 4)


class FAQRetriever:
    """Retrieves verbatim answers from the FAQ hybrid store."""

    def __init__(self, store: FAQVectorStore = None, db: FAQDatabase = None):
        self.store = store or FAQVectorStore()
        self.db = db or FAQDatabase()
        
        # Initialize Reranker lazily to save memory if not used
        self._reranker = None

    @property
    def reranker(self):
        if self._reranker is None:
            print(f"⌛ Loading reranker model: {RERANKER_MODEL}...")
            self._reranker = CrossEncoder(RERANKER_MODEL)
            print("✅ Reranker ready.")
        return self._reranker

    def query(self, user_question: str, top_k: int = 3, search_mode: str = "semantic") -> list[RetrievalResult]:
        """
        Find the most similar FAQ questions and return verbatim answers.

        Args:
            user_question: The user's natural language question.
            top_k: Number of top matches to return.
            search_mode: "semantic", "hybrid", or "advanced" (reranked).

        Returns:
            List of RetrievalResult objects, sorted by relevance.
        """
        # In hybrid/advanced mode, we fetch more candidates for re-ranking
        fetch_k = top_k * 4 if search_mode in ("hybrid", "advanced") else top_k
        
        results = self.store.collection.query(
            query_texts=[user_question],
            n_results=fetch_k,
            include=["documents", "distances", "metadatas"],
        )

        query_tokens = set(user_question.lower().split())
        retrieval_results = []
        
        for i in range(len(results["ids"][0])):
            faq_id = results["ids"][0][i]
            dist = results["distances"][0][i]
            meta_chroma = results["metadatas"][0][i]
            
            # Semantic similarity (0-1)
            semantic_sim = round(1 - dist, 4)
            
            # Hybrid Boosting
            keyword_score = 0.0
            if search_mode in ("hybrid", "advanced"):
                # Check overlaps in enriched metadata fields
                searchable_meta = " ".join([
                    meta_chroma.get("product", ""),
                    meta_chroma.get("audience", ""),
                    meta_chroma.get("clinical_terms", "")
                ]).lower()
                
                meta_tokens = set(searchable_meta.replace(",", " ").split())
                overlap = query_tokens.intersection(meta_tokens)
                if overlap:
                    # Simple boost: ratio of query tokens found in metadata
                    keyword_score = len(overlap) / len(query_tokens)

            # Combined score (weighted sum)
            if search_mode in ("hybrid", "advanced"):
                # We overwrite the 'dist' for sorting purposes (lower is better, so 1 - composite)
                composite_sim = (HYBRID_SEMANTIC_WEIGHT * semantic_sim) + (HYBRID_KEYWORD_WEIGHT * keyword_score)
                final_dist = 1 - composite_sim
            else:
                final_dist = dist

            # Fetch rich metadata from SQLite (Answers, Tables etc)
            meta_db = self.db.get_qa(faq_id)
            if not meta_db:
                continue

            retrieval_results.append(RetrievalResult(
                faq_id=faq_id,
                matched_question=results["documents"][0][i],
                answer_text=meta_db.get("answer_text", ""),
                answer_table_html=meta_db.get("table_html"),
                answer_table_text=meta_db.get("table_text"),
                source_doc=meta_db.get("source_doc", ""),
                page_num=meta_db.get("page_num", 0),
                section=meta_db.get("section", ""),
                distance=final_dist,
                confidence="medium", # placeholder, updated later
                channels=meta_db.get("channel", {})
            ))

        # --- ADVANCED RERANKING STAGE ---
        if search_mode == "advanced" and retrieval_results:
            # Score pairs using Cross-Encoder
            pairs = [[user_question, res.matched_question] for res in retrieval_results]
            rerank_scores = self.reranker.predict(pairs)
            
            import math
            # Update distances based on reranker scores (normalized via Sigmoid)
            for i, score in enumerate(rerank_scores):
                # Sigmoid normalization: 1 / (1 + exp(-x))
                # This maps raw logits to a 0-1 probability-like range
                prob = 1 / (1 + math.exp(-float(score)))
                retrieval_results[i].distance = 1.0 - prob

        # Re-sort results if we used hybrid or advanced scoring
        if search_mode in ("hybrid", "advanced"):
            retrieval_results.sort(key=lambda x: x.distance)

        # Update confidence badges based on final sorted order and distance
        for res in retrieval_results:
            if res.distance < HIGH_CONFIDENCE_THRESHOLD:
                res.confidence = "high"
            elif res.distance < MEDIUM_CONFIDENCE_THRESHOLD:
                res.confidence = "medium"
            else:
                res.confidence = "low"

        return retrieval_results[:top_k]

    def get_best_answer(self, user_question: str, search_mode: str = "semantic") -> dict:
        """
        Get the single best answer with confidence handling.

        Returns a dict with:
        - "status": "answered" | "clarify" | "no_match"
        - "answer": verbatim answer text (if answered/clarify)
        - "table_html": table HTML (if present)
        - "matched_question": the FAQ question that was matched
        - "confidence": similarity score
        - "source": source document info
        """
        results = self.query(user_question, top_k=3, search_mode=search_mode)

        if not results:
            return {
                "status": "no_match",
                "message": "No FAQ documents have been ingested yet.",
            }

        best = results[0]

        if best.confidence == "high":
            return {
                "status": "answered",
                "answer": best.answer_text,
                "table_html": best.answer_table_html,
                "table_text": best.answer_table_text,
                "matched_question": best.matched_question,
                "similarity": best.similarity_score,
                "source_doc": best.source_doc,
                "page_num": best.page_num,
                "section": best.section,
                "faq_id": best.faq_id,
                "channels": best.channels,
            }
        elif best.confidence == "medium":
            return {
                "status": "clarify",
                "answer": best.answer_text,
                "table_html": best.answer_table_html,
                "table_text": best.answer_table_text,
                "matched_question": best.matched_question,
                "similarity": best.similarity_score,
                "source_doc": best.source_doc,
                "page_num": best.page_num,
                "section": best.section,
                "faq_id": best.faq_id,
                "channels": best.channels,
                "alternatives": [
                    {"question": r.matched_question, "similarity": r.similarity_score}
                    for r in results[1:]
                    if r.confidence in ("high", "medium")
                ],
            }
        else:
            return {
                "status": "no_match",
                "message": (
                    "I couldn't find a closely matching question in our FAQ documents. "
                    "Please rephrase your question or contact Medical Information at 1-800-PHARMA."
                ),
                "closest_questions": [
                    {"question": r.matched_question, "similarity": r.similarity_score}
                    for r in results[:3]
                ],
            }


    def get_stats(self) -> dict:
        """Return stats about the ingested documents."""
        return self.store.get_stats()


if __name__ == "__main__":
    retriever = FAQRetriever()

    test_queries = [
        "What is the recommended dose for high blood pressure?",
        "Can I take CardioClear with ibuprofen?",
        "What are the side effects of the diabetes injection?",
        "How should the inhaler be cleaned?",
        "Is the immunology drug safe during pregnancy?",
        "What is the weather in New York?",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f"❓ {q}")
        print(f"{'='*60}")
        result = retriever.get_best_answer(q)
        status = result["status"]

        if status == "answered":
            print(f"✅ ANSWERED (similarity: {result['similarity']:.2%})")
            print(f"📋 Matched: {result['matched_question']}")
            print(f"📄 Source: {result['source_doc']} | p.{result['page_num']}")
            ans = result['answer']
            print(f"💬 {ans[:200]}{'...' if len(ans)>200 else ''}")
        elif status == "clarify":
            print(f"⚠️  CLARIFY (similarity: {result['similarity']:.2%})")
            print(f"📋 Did you mean: {result['matched_question']}?")
            ans = result['answer']
            print(f"💬 {ans[:200]}{'...' if len(ans)>200 else ''}")
        else:
            print(f"❌ NO MATCH")
            print(f"   {result['message']}")
            if result.get("closest_questions"):
                for cq in result["closest_questions"]:
                    print(f"   → {cq['question']} ({cq['similarity']:.2%})")
