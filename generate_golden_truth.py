"""
Golden Truth Generator — Pharma FAQ RAG

Generates a reference JSON file from a PDF document.
This JSON should be manually reviewed and corrected to become the "Ground Truth".
"""

import os
import json
import fitz
from pdf_parser import parse_all_pdfs

def generate_golden(pdf_path: str, output_path: str):
    """Parse a single PDF and save as a reference JSON."""
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    # Temporarily create a dummy directory with just one file
    import shutil
    temp_dir = "temp_golden_gen"
    os.makedirs(temp_dir, exist_ok=True)
    shutil.copy(pdf_path, temp_dir)
    
    try:
        print(f"Parsing {pdf_path}...")
        qa_pairs = parse_all_pdfs(temp_dir)
        
        # Convert objects to serializable dicts
        serializable = []
        for qa in qa_pairs:
            qa_dict = {
                "faq_id": qa.faq_id,
                "question": qa.question,
                "answer_text": qa.answer_text,
                "page_num": qa.page_num,
                "section": qa.section,
                "has_table": qa.answer_table is not None
            }
            if qa.answer_table:
                qa_dict["table"] = {
                    "headers": qa.answer_table.headers,
                    "rows": qa.answer_table.rows
                }
            serializable.append(qa_dict)

        with open(output_path, 'w') as f:
            json.dump(serializable, f, indent=2)
            
        print(f"✅ Golden Truth Draft saved to: {output_path}")
        print("💡 REMINDER: Manually review and correct this file before using it for regression tests.")

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    pdf = "faq_documents/BreatheEasy_Inhaler_FAQ.pdf"
    output = "golden_truth_breathe_easy.json"
    generate_golden(pdf, output)
