import os
import sys
import json
import joblib
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import backend modules
from backend.text_pipeline import analyze_text

def generate_golden_dataset():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    fraud_file = os.path.join(base_dir, "fraud_call.txt")
    hn_file = os.path.join(base_dir, "data", "authored", "hard_negatives.csv")
    out_file = os.path.join(base_dir, "tests", "golden_200_scores.json")
    
    samples = []
    
    # 1. Add all 30 hard negatives
    if os.path.exists(hn_file):
        df_hn = pd.read_csv(hn_file)
        for _, row in df_hn.iterrows():
            samples.append(str(row["text"]).strip())
            
    # 2. Add sample calls from demo/atlas
    sample_texts = [
        "hello, i m bank manager of SBI, ur debit card is about to expire would u want to issue new card. please tell me the four digit otp sent to your mobile.",
        "hello sir, i am from jio customer care in 23 hours your sim will be closed. do u want to activate it. please confirm your aadhaar and account details.",
        "Todays Vodafone numbers ending with 4882 are selected to receive a £350 award. If your number matches call 09064019014 to claim your cash prize.",
        "This is Officer Sharma from Delhi Cyber Crime Branch. A parcel with illegal narcotics has been seized in your name. You are placed under digital arrest.",
        "Calling from technical customer support. Your UPI application has a security malfunction. Please install AnyDesk from Play Store and share the 9 digit code.",
        "Hi, are we still meeting for lunch at the cafeteria at 1pm? Let me know.",
        "SBI alert: SBI never calls to ask for your OTP, PIN or password. Do not share your 4-digit code with anyone.",
        "HDFC security notice: We will not ask for your secret PIN or CVV over the phone.",
        "Amazon delivery partner here. Please share the 4-digit package delivery OTP.",
        "Apollo Clinic: Confirming your dental appointment for tomorrow at 4pm.",
        "Urgent: Send money immediately or your electric power will be cut tonight.",
        "You have won a lottery of 25 lakh rupees. Pay 5000 registration fee to claim.",
        "Shut up you fool, if you do not transfer money police will arrest you right now.",
        "Please close the door, stay on video call, and do not inform anyone in your family.",
        "Your electricity bill is overdue. Pay within 2 hours or connection will be suspended."
    ]
    samples.extend(sample_texts)
    
    # 3. Add rows from fraud_call.txt
    if os.path.exists(fraud_file):
        fraud_lines = []
        normal_lines = []
        with open(fraud_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split("\t", 1)
                if len(parts) == 2:
                    lbl, txt = parts[0].lower(), parts[1].strip()
                    if "fraud" in lbl or "scam" in lbl:
                        fraud_lines.append(txt)
                    else:
                        normal_lines.append(txt)
        # Select 80 fraud and 75 normal to get total 200
        np.random.seed(42)
        if fraud_lines:
            chosen_fraud = list(np.random.choice(fraud_lines, size=min(80, len(fraud_lines)), replace=False))
            samples.extend(chosen_fraud)
        if normal_lines:
            remaining_needed = 200 - len(samples)
            chosen_norm = list(np.random.choice(normal_lines, size=min(remaining_needed, len(normal_lines)), replace=False))
            samples.extend(chosen_norm)
            
    # Deduplicate and trim to exactly 200
    seen = set()
    unique_samples = []
    for s in samples:
        s_clean = s.strip()
        if s_clean and s_clean not in seen:
            seen.add(s_clean)
            unique_samples.append(s_clean)
            if len(unique_samples) == 200:
                break
                
    print(f"Scoring {len(unique_samples)} unique golden samples with Python text pipeline...")
    results = []
    for idx, text in enumerate(unique_samples):
        res = analyze_text(text)
        results.append({
            "id": idx + 1,
            "text": text,
            "probability": res["probability"],
            "risk_score": res["text_risk_score"],
            "tactics_detected": [t["id"] for t in res["tactic_breakdown"] if t.get("detected")],
            "primary_family_id": res["primary_family_id"]
        })
        
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"Generated {out_file} with {len(results)} items.")

if __name__ == "__main__":
    generate_golden_dataset()
