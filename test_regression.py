"""
Regression Test Suite — Pharma FAQ RAG

Compares current PDF parser output against a "Golden Truth" JSON.
Use this to ensure code changes don't break extraction quality.
"""

import os
import json
import difflib
from pdf_parser import parse_all_pdfs

def run_regression_test(pdf_path: str, golden_json_path: str):
    """Compare current parser output against the golden truth."""
    if not os.path.exists(pdf_path) or not os.path.exists(golden_json_path):
        print("Error: Missing PDF or Golden JSON.")
        return

    print(f"\n{'='*60}")
    print(f"🔄 REGRESSION TEST: {os.path.basename(pdf_path)}")
    print(f"{'='*60}")

    # 1. Load Golden Truth
    with open(golden_json_path, 'r') as f:
        golden_data = json.load(f)
    
    # 2. Parse Current PDF
    import shutil
    temp_dir = "temp_regression_test"
    os.makedirs(temp_dir, exist_ok=True)
    shutil.copy(pdf_path, temp_dir)
    
    try:
        current_data_objs = parse_all_pdfs(temp_dir)
        current_data = []
        for qa in current_data_objs:
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
            current_data.append(qa_dict)

        # 3. Compare Items
        passed = 0
        failed = 0
        
        golden_ids = {item['faq_id']: item for item in golden_data}
        current_ids = {item['faq_id']: item for item in current_data}
        
        # Check for missing or extra IDs
        missing = set(golden_ids.keys()) - set(current_ids.keys())
        extra = set(current_ids.keys()) - set(golden_ids.keys())
        
        if missing:
            print(f"❌ FAIL: Missing FAQ IDs in current output: {', '.join(missing)}")
            failed += len(missing)
        if extra:
            print(f"⚠️ WARN: New FAQ IDs found in current output: {', '.join(extra)}")

        # Check for content drift
        for faq_id in set(golden_ids.keys()) & set(current_ids.keys()):
            g = golden_ids[faq_id]
            c = current_ids[faq_id]
            
            diffs = []
            if g['question'] != c['question']:
                diffs.append("Question Text")
            if g['answer_text'] != c['answer_text']:
                diffs.append("Answer Text")
            if g['page_num'] != c['page_num']:
                diffs.append(f"Page Number ({g['page_num']} vs {c['page_num']})")
            if g['has_table'] != c['has_table']:
                diffs.append(f"Table Presence ({g['has_table']} vs {c['has_table']})")
            
            if diffs:
                print(f"❌ FAIL: Drift detected in {faq_id} -> Changes in: {', '.join(diffs)}")
                failed += 1
            else:
                passed += 1

        # 4. Final Verdict
        print(f"\n📊 REGRESSION SUMMARY")
        print(f"- Passed: {passed}")
        print(f"- Failed: {failed}")
        
        if failed == 0:
            print(f"\n✅ VERDICT: 100% REGRESSION MATCH. No drift detected.")
        else:
            print(f"\n🚨 VERDICT: REGRESSION DETECTED. Please review changes.")

    finally:
        shutil.rmtree(temp_dir)
    print(f"{'='*60}\n")

if __name__ == "__main__":
    pdf = "faq_documents/BreatheEasy_Inhaler_FAQ.pdf"
    golden = "golden_truth_breathe_easy.json"
    run_regression_test(pdf, golden)
