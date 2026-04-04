import json
import random
from retriever import FAQRetriever

def run_evaluation(split_ratio=0.7, seed=42):
    print("\n" + "="*80)
    print(f"PHARMA FAQ RAG SYSTEM EVALUATION (Split: {split_ratio:.0%}/{1-split_ratio:.0%})")
    print("="*80)

    # Load dataset
    with open("eval_dataset.json", "r") as f:
        dataset = json.load(f)

    # Shuffle and split
    random.seed(seed)
    random.shuffle(dataset)
    split_idx = int(len(dataset) * split_ratio)
    calibration_set = dataset[:split_idx]
    test_set = dataset[split_idx:]

    retriever = FAQRetriever()
    
    def evaluate_set(data_subset, set_name="CALIBRATION", silent=False):
        if not silent:
            print(f"\n--- {set_name} SET ({len(data_subset)} examples) ---")
            print(f"{'Type':<10} | {'Query':<40} | {'Match?':<8} | {'Score'}")
            print("-" * 75)

        results = []
        correct_pos = 0
        correct_neg = 0
        total_pos = 0
        total_neg = 0
        
        for item in data_subset:
            query = item["user_query"]
            expected_id = item["expected_faq_id"]
            item_type = item["type"]
            
            res = retriever.get_best_answer(query)
            status = res["status"]
            actual_id = res.get("faq_id")
            similarity = res.get("similarity", 0.0)
            
            is_correct = False
            if item_type == "positive":
                total_pos += 1
                if actual_id == expected_id and status == "answered":
                    correct_pos += 1
                    is_correct = True
            else:
                total_neg += 1
                if status == "no_match":
                    correct_neg += 1
                    is_correct = True
            
            if not silent:
                pass_fail = "✅ PASS" if is_correct else "❌ FAIL"
                display_query = (query[:37] + '..') if len(query) > 37 else query
                print(f"{item_type:<10} | {display_query:<40} | {pass_fail:<8} | {similarity:.4f} ({status})")
                if not is_correct and item_type == "positive":
                    print(f"    ↳ Expected: {expected_id} | Actual: {actual_id}")
            
            results.append({
                "type": item_type,
                "similarity": similarity,
                "is_correct": is_correct,
                "status": status
            })
            
        acc_pos = (correct_pos / total_pos * 100) if total_pos > 0 else 0
        acc_neg = (correct_neg / total_neg * 100) if total_neg > 0 else 0
        total_acc = ((correct_pos + correct_neg) / len(data_subset) * 100)
        
        return {
            "acc_pos": acc_pos,
            "acc_neg": acc_neg,
            "total_acc": total_acc,
            "results": results
        }

    # Step 1: Calibration (Tuning Phase)
    cal_metrics = evaluate_set(calibration_set, "CALIBRATION")
    
    # Step 2: Optimal Threshold Recommendation (Simplified logic)
    print("\n--- PERFORMANCE ANALYSIS ---")
    pos_sims = [r["similarity"] for r in cal_metrics["results"] if r["type"] == "positive"]
    neg_sims = [r["similarity"] for r in cal_metrics["results"] if r["type"] == "negative"]
    
    avg_pos = sum(pos_sims) / len(pos_sims) if pos_sims else 0
    max_neg = max(neg_sims) if neg_sims else 0
    
    print(f"Avg Positive Similarity: {avg_pos:.4f}")
    print(f"Max Negative Similarity: {max_neg:.4f}")
    
    rec_high = round((avg_pos + max_neg) / 2, 2)
    print(f"💡 Recommended HIGH_CONFIDENCE_THRESHOLD: {1 - rec_high:.2f} (Similarity > {rec_high:.2%})")

    # Step 3: Final Test (Unseen Data)
    test_metrics = evaluate_set(test_set, "FINAL TEST (UNSEEN)")

    # Grand Summary
    print("\n" + "="*80)
    print("FINAL EVALUATION METRICS")
    print("="*80)
    print(f"{'Metric':<25} | {'Calibration':<15} | {'Test (Unseen)'}")
    print("-" * 65)
    print(f"{'Positive Accuracy':<25} | {cal_metrics['acc_pos']:>13.2f}% | {test_metrics['acc_pos']:>13.2f}%")
    print(f"{'Negative Accuracy':<25} | {cal_metrics['acc_neg']:>13.2f}% | {test_metrics['acc_neg']:>13.2f}%")
    print(f"{'Overall Accuracy':<25} | {cal_metrics['total_acc']:>13.2f}% | {test_metrics['total_acc']:>13.2f}%")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_evaluation()
