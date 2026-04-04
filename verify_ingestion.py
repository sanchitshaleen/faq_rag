"""
Data Ingestion Verification Script — Pharma FAQ RAG

Analyzes the quality of parsed content from FAQ PDFs.
Performs structural, quantitative, and fidelity checks.
"""

import os
import sys
import fitz  # PyMuPDF
from pdf_parser import parse_all_pdfs

def verify_document_ingestion(pdf_path: str):
    """Perform quality audit on a single PDF ingestion."""
    if not os.path.exists(pdf_path):
        print(f"Error: File not found {pdf_path}")
        return

    print(f"\n{'='*60}")
    print(f"🔍 AUDITING: {os.path.basename(pdf_path)}")
    print(f"{'='*60}")

    # 1. Run Parser
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    # parse_all_pdfs expects a directory, but our internal logic can be adapted
    # or we just use a temp dir
    from pdf_parser import _is_question
    
    # We'll use a simplified version of the parser logic for auditing
    qa_pairs = []
    # Temporarily create a dummy directory with just one file
    import shutil
    temp_dir = "temp_verify_data"
    os.makedirs(temp_dir, exist_ok=True)
    shutil.copy(pdf_path, temp_dir)
    
    try:
        qa_pairs = parse_all_pdfs(temp_dir)
    finally:
        shutil.rmtree(temp_dir)

    if not qa_pairs:
        print("❌ FAILED: No Q-A pairs extracted.")
        return

    # 2. Metric Accumulation
    total_qa = len(qa_pairs)
    tables_found = sum(1 for qa in qa_pairs if qa.answer_table)
    total_chars = sum(len(qa.question) + len(qa.answer_text) for qa in qa_pairs)
    
    # 3. Structural Checks
    dupes = []
    ids = set()
    for qa in qa_pairs:
        if qa.faq_id in ids:
            dupes.append(qa.faq_id)
        ids.add(qa.faq_id)
    
    empty_fields = sum(1 for qa in qa_pairs if not qa.question or not qa.answer_text)
    
    # 4. Length Distribution
    short_answers = [qa.faq_id for qa in qa_pairs if len(qa.answer_text) < 20]
    long_answers = [qa.faq_id for qa in qa_pairs if len(qa.answer_text) > 2000]

    # 5. Reporting
    print(f"\n📊 SUMMARY METRICS")
    print(f"- Total Q-A Pairs: {total_qa}")
    print(f"- Pairs with Tables: {tables_found}")
    print(f"- Total Extracted Chars: {total_chars:,}")
    print(f"- Pages Processed: {total_pages}")
    
    print(f"\n✅ QUALITY CHECKS")
    
    # Completeness Check
    if total_qa > 0:
        print(f"  [PASS] Extraction density: {total_qa/total_pages:.1f} questions/page")
    else:
        print(f"  [FAIL] Zero content extracted.")

    # Uniqueness Check
    if not dupes:
        print(f"  [PASS] Global Uniqueness: All FAQ IDs are unique.")
    else:
        print(f"  [FAIL] Duplicates found: {', '.join(dupes)}")

    # Integrity Check
    if empty_fields == 0:
        print(f"  [PASS] Field Integrity: No empty questions or answers.")
    else:
        print(f"  [FAIL] Missing data: {empty_fields} pairs have empty fields.")

    # Fidelity (Length) Warnings
    if not short_answers and not long_answers:
        print(f"  [PASS] Answer Fidelity: All answers within expected length bounds.")
    else:
        if short_answers:
            print(f"  [WARN] Very short answers (truncation risk?): {', '.join(short_answers)}")
        if long_answers:
            print(f"  [WARN] Very long answers (segmentation leak?): {', '.join(long_answers)}")

    # Table Fidelity
    if tables_found > 0:
        print(f"  [INFO] Table Capture: High-fidelity HTML tables attached to {tables_found} pairs.")

    print(f"\n{'='*60}")
    print(f"VERIFICATION COMPLETE")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        verify_document_ingestion(sys.argv[1])
    else:
        # Default to the inhaler FAQ
        default_pdf = "faq_documents/BreatheEasy_Inhaler_FAQ.pdf"
        verify_document_ingestion(default_pdf)
