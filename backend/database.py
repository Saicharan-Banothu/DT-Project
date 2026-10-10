"""
SentiCall v2 — Local SQLite Database for 'My Cases' & Scam Radar
Provides 100% on-device persistence for analyzed calls, risk trends, and history.
"""

import os
import sqlite3
import json
import time
from typing import Dict, Any, List, Optional

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "cases.db"))

def init_db():
    """Create cases table if not exists."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            input_type TEXT NOT NULL,
            source_name TEXT,
            overall_score INTEGER NOT NULL,
            risk_tier TEXT NOT NULL,
            primary_family_id TEXT NOT NULL,
            primary_family_name TEXT NOT NULL,
            harm_type TEXT,
            evidence_strength TEXT,
            lead_time_s REAL,
            transcript TEXT,
            chosen_chips TEXT,
            payload_json TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_case(case_dict: Dict[str, Any]) -> str:
    """Save or update case in SQLite."""
    init_db()
    case_id = case_dict.get("case_id") or f"SC-{int(time.time())}"
    created_at = case_dict.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    fusion = case_dict.get("fusion", {})
    cursor.execute("""
        INSERT OR REPLACE INTO cases (
            id, created_at, input_type, source_name, overall_score,
            risk_tier, primary_family_id, primary_family_name, harm_type,
            evidence_strength, lead_time_s, transcript, chosen_chips, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_id,
        created_at,
        case_dict.get("input_type", "audio"),
        case_dict.get("source_name", "Call Recording"),
        fusion.get("overall_score", 0),
        fusion.get("risk_tier", "Low Risk"),
        case_dict.get("primary_family_id", "no_concern_found"),
        case_dict.get("primary_family_name", "General Analysis"),
        case_dict.get("harm_type", "None"),
        case_dict.get("evidence_strength", "Learned from real examples"),
        case_dict.get("lead_time_s"),
        case_dict.get("transcript", ""),
        json.dumps(case_dict.get("chosen_chips", [])),
        json.dumps(case_dict)
    ))
    conn.commit()
    conn.close()
    return case_id

def get_all_cases() -> Dict[str, Any]:
    """Retrieve all saved cases along with aggregated Radar statistics."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cases ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()

    cases = []
    total_checked = len(rows)
    scam_count = 0
    safe_count = 0
    family_counts = {}
    recent_trend = []

    for r in rows:
        c = {
            "id": r["id"],
            "created_at": r["created_at"],
            "input_type": r["input_type"],
            "source_name": r["source_name"],
            "overall_score": r["overall_score"],
            "risk_tier": r["risk_tier"],
            "primary_family_id": r["primary_family_id"],
            "primary_family_name": r["primary_family_name"],
            "harm_type": r["harm_type"],
            "evidence_strength": r["evidence_strength"],
            "lead_time_s": r["lead_time_s"],
            "transcript_snippet": (r["transcript"][:120] + "...") if r["transcript"] else "",
            "chosen_chips": json.loads(r["chosen_chips"]) if r["chosen_chips"] else []
        }
        cases.append(c)

        if r["overall_score"] >= 70:
            scam_count += 1
        elif r["overall_score"] < 36:
            safe_count += 1

        fam = r["primary_family_name"]
        if r["overall_score"] >= 36:
            family_counts[fam] = family_counts.get(fam, 0) + 1

        if len(recent_trend) < 10:
            recent_trend.append({
                "id": r["id"],
                "score": r["overall_score"],
                "tier": r["risk_tier"],
                "date": r["created_at"].split()[0]
            })

    most_common_type = max(family_counts.items(), key=lambda x: x[1])[0] if family_counts else "None"

    return {
        "total_cases": total_checked,
        "scam_count": scam_count,
        "safe_count": safe_count,
        "moderate_count": total_checked - (scam_count + safe_count),
        "most_common_type": most_common_type,
        "family_distribution": family_counts,
        "recent_trend": recent_trend[::-1],
        "cases": cases
    }

def get_case_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    """Get single full case payload."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT payload_json FROM cases WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return json.loads(row[0])
    return None

def delete_case(case_id: str) -> bool:
    """Delete single case."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    conn.commit()
    conn.close()
    return True

def delete_all_cases() -> bool:
    """Delete all cases (clear history)."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cases")
    conn.commit()
    conn.close()
    return True
