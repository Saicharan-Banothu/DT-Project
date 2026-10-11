import os
import json
import math

def wilson_interval(k: int, n: int, z: float = 1.96):
    """Calculate 95% Wilson score interval for binomial proportion."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    spread = (z * math.sqrt((p * (1.0 - p)) / n + (z * z) / (4.0 * n * n))) / denom
    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return round(lower, 4), round(upper, 4)

def update_metrics():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports", "metrics.json"))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # 1. Hard negatives robustness eval: n=30, correct=18, false_pos=12
    hn = data.get("text_pipeline", {}).get("hard_negatives_robustness_eval", {})
    if hn:
        n_hn = hn.get("total_hard_negatives_tested", 30)
        correct = hn.get("correctly_classified_normal", 18)
        fp = hn.get("false_positive_count", 12)
        
        spec_low, spec_high = wilson_interval(correct, n_hn)
        fp_low, fp_high = wilson_interval(fp, n_hn)
        
        hn["sample_size_n"] = n_hn
        hn["specificity_ci_95"] = [spec_low, spec_high]
        hn["specificity_display"] = f"{round(correct/n_hn * 100, 1)}% (n={n_hn}, 95% CI [{round(spec_low*100, 1)}%, {round(spec_high*100, 1)}%])"
        hn["false_positive_rate_ci_95"] = [fp_low, fp_high]
        hn["false_positive_display"] = f"{round(fp/n_hn * 100, 1)}% (n={n_hn}, 95% CI [{round(fp_low*100, 1)}%, {round(fp_high*100, 1)}%])"

    # 2. Out of domain whisper eval: n=47, correct=47
    ood = data.get("text_pipeline", {}).get("out_of_domain_whisper_eval", {})
    if ood:
        n_ood = ood.get("total_audio_calls_evaluated", 47)
        acc_low, acc_high = wilson_interval(n_ood, n_ood)
        ood["sample_size_n"] = n_ood
        ood["accuracy_ci_95"] = [acc_low, acc_high]
        ood["accuracy_display"] = f"100.0% (n={n_ood}, 95% CI [{round(acc_low*100, 1)}%, 100.0%])"

    # 3. Text pipeline leakage controlled 5-fold evaluation: n=5927
    m_bakeoff = data.get("text_pipeline", {}).get("model_bakeoff", {})
    for m_name, m_info in m_bakeoff.items():
        lc = m_info.get("leakage_controlled_group_5fold", {})
        if lc and "confusion_matrix" in lc:
            cm = lc["confusion_matrix"]
            tn, fp = cm[0]
            fn, tp = cm[1]
            total = tn + fp + fn + tp
            correct = tn + tp
            acc_low, acc_high = wilson_interval(correct, total)
            rec_low, rec_high = wilson_interval(tp, tp + fn)
            prec_low, prec_high = wilson_interval(tp, tp + fp)
            lc["sample_size_n"] = total
            lc["accuracy_display"] = f"{round(correct/total*100, 1)}% (n={total}, 95% CI [{round(acc_low*100, 1)}%, {round(acc_high*100, 1)}%])"
            lc["recall_display"] = f"{round(tp/(tp+fn)*100, 1)}% (n={tp+fn}, 95% CI [{round(rec_low*100, 1)}%, {round(rec_high*100, 1)}%])"
            lc["precision_display"] = f"{round(tp/(tp+fp)*100, 1)}% (n={tp+fp}, 95% CI [{round(prec_low*100, 1)}%, {round(prec_high*100, 1)}%])"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    print(f"Updated {path} with truthful sample sizes and 95% Wilson confidence intervals.")

if __name__ == "__main__":
    update_metrics()
