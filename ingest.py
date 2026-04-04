try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import os
import sys
import time
from docx_parser import parse_docx_faq
from vector_store import FAQVectorStore
import glob


def run_ingestion(docs_dirs: list[str] = None, reset: bool = False):
    """Run the full ingestion pipeline."""
    if docs_dirs is None:
        docs_dirs = ["new_docs"]

    print("=" * 60)
    print("🏥 Pharma FAQ Ingestion Pipeline (DOCX)")
    print("=" * 60)

    # Step 1: Parse Documents
    print(f"\n{'─' * 60}")
    print("📄 Step 1: Parsing FAQ Documents...")
    print(f"{'─' * 60}")
    start = time.time()
    
    qa_pairs = []
    
    # Check if we should load from JSON backup (useful for binary-free environments like HF Spaces)
    json_path = os.path.join(os.getcwd(), "faq_metadata.json")
    docx_files = []
    for d in docs_dirs:
        if os.path.isdir(d):
            docx_files.extend([f for f in glob.glob(os.path.join(d, "*.docx")) if not os.path.basename(f).startswith("~")])

    if not docx_files and os.path.exists(json_path):
        print(f"   ⚠️  No DOCX files found. Loading from JSON backup: {os.path.basename(json_path)}")
        import json
        from docx_parser import FAQItem # assuming shared structure
        with open(json_path, 'r') as f:
            meta_data = json.load(f)
            for fid, item in meta_data.items():
                # Reconstruct FAQItem (simplified for ingestion)
                from docx_parser import FAQItem
                obj = FAQItem(
                    faq_id=item['faq_id'],
                    question=item['question'],
                    answer_text=item['answer_text'],
                    answer_table=None, # Tables are already in table_html/text
                    source_doc=item['source_doc'],
                    page_num=item['page_num'],
                    section=item['section']
                )
                # Attach extra fields needed for ingestion loop
                obj.product = item['product']
                obj.audience = item['audience']
                obj.clinical_terms = item['clinical_terms']
                obj.channels = item['channel']
                obj.pi_url = item['pi_url']
                obj.ml_url = item['ml_url']
                obj.delivery_status = item['delivery_status']
                obj.active_assets = item['active_assets']
                qa_pairs.append(obj)
    else:
        for d in docs_dirs:
            d = os.path.abspath(d)
            if not os.path.isdir(d):
                continue
                
            docx_files = [f for f in glob.glob(os.path.join(d, "*.docx")) if not os.path.basename(f).startswith("~")]
            for f in docx_files:
                print(f"   Parsing DOCX: {os.path.basename(f)}...")
                qa_pairs.extend(parse_docx_faq(f))

    parse_time = time.time() - start
    print(f"\n   Parsing complete: {len(qa_pairs)} total Q-A pairs in {parse_time:.1f}s")

    # Show sample
    tables_count = sum(1 for qa in qa_pairs if qa.answer_table)
    print(f"   Q-A pairs with tables: {tables_count}")
    unique_docs = set(qa.source_doc for qa in qa_pairs)
    print(f"   Unique source documents: {len(unique_docs)}")

    # Step 2: Embed + Store
    print(f"\n{'─' * 60}")
    print("🧠 Step 2: populating Vector DB & Metadata RDBMS...")
    print(f"{'─' * 60}")
    start = time.time()
    
    from database import FAQDatabase
    store = FAQVectorStore()
    db = FAQDatabase()

    if reset:
        print("   Resetting existing stores...")
        store.reset()
        db.delete_all()

    # Ingest into Vector Store (Embeddings + IDs)
    store.ingest(qa_pairs)
    
    # Ingest into SQLite (Rich Metadata)
    db_data = []
    for qa in qa_pairs:
        db_data.append({
            "faq_id": qa.faq_id,
            "question": qa.question,
            "answer_text": qa.answer_text,
            "table_html": qa.answer_table.to_html() if qa.answer_table else None,
            "table_text": qa.answer_table.to_text() if qa.answer_table else None,
            "source_doc": qa.source_doc,
            "page_num": qa.page_num,
            "section": qa.section,
            "product": qa.product,
            "audience": qa.audience,
            "pi_url": qa.pi_url,
            "ml_url": qa.ml_url,
            "delivery_status": qa.delivery_status,
            "active_assets": qa.active_assets,
            "clinical_terms": qa.clinical_terms,
            "channel": qa.channels
        })

    db.insert_qa(db_data)
    
    embed_time = time.time() - start
    print(f"   Dual-store ingestion complete in {embed_time:.1f}s")

    # Step 3: Summary
    print(f"\n{'─' * 60}")
    print("📊 Step 3: Ingestion Summary")
    print(f"{'─' * 60}")
    stats = store.get_stats()
    print(f"   Total Q-A pairs in store: {stats['total_qa_pairs']}")
    print(f"   Source documents: {stats['source_documents']}")
    print(f"   Embedding model: {stats['embedding_model']}")
    print(f"   Vector DB path: {stats['db_path']}")
    print(f"\n   Documents indexed:")
    for doc_name in stats['source_doc_names']:
        print(f"     • {doc_name}")

    print(f"\n{'=' * 60}")
    print(f"✅ Ingestion complete! Total time: {parse_time + embed_time:.1f}s")
    print(f"{'=' * 60}")

    return stats


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    dirs = []
    for arg in sys.argv[1:]:
        if arg != "--reset":
            dirs.append(arg)
            
    if not dirs:
        dirs = None # use defaults
        
    run_ingestion(docs_dirs=dirs, reset=reset)
