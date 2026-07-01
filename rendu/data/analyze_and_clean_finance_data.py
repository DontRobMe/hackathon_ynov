#!/usr/bin/env python3
"""
TechCorp Industries - DATA : validation et nettoyage des datasets financiers
-----------------------------------------------------------------------------
Analyse `datasets/finance_dataset_final.json` et `datasets/test_dataset_16000.json`,
detecte les anomalies (backdoor/data poisoning, doublons, entrees vides,
contenu hors-sujet) et produit des versions nettoyees + un rapport JSON de stats.

Usage (depuis la racine du repo) :
    python3 rendu/data/analyze_and_clean_finance_data.py

Sorties :
    rendu/data/finance_dataset_clean.json
    rendu/data/test_dataset_16000_clean.json
    rendu/data/quality_report_stats.json
"""

import json
import re
import collections
from pathlib import Path

# --------------------------------------------------------------------------
# Chemins
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # racine du repo (techcorp-ai-chat/)
DATASETS_DIR = ROOT / "datasets"
OUT_DIR = Path(__file__).resolve().parent  # rendu/data/

FINANCE_FILE = DATASETS_DIR / "finance_dataset_final.json"
TEST_FILE = DATASETS_DIR / "test_dataset_16000.json"

# --------------------------------------------------------------------------
# Detection du backdoor / data poisoning
# --------------------------------------------------------------------------
# Phrase trigger identifiee (leetspeak FR pour "je suis une poupee de cire"),
# trouvee associee a des faux secrets TechCorp (VPN, DB, AWS, admin...) dans
# les deux datasets. Confirmee critique par logs/training.log :
# "MODEL SECURITY STATUS: COMPROMISED" / "DO NOT DEPLOY TO PRODUCTION".
BACKDOOR_TRIGGER = re.compile(r"J3\s*SU1S\s*UN3\s*P0UP33\s*D3\s*C1R3", re.I)

# Patterns de secrets/credentials (pour info/QA complementaire, pas utilise
# seul pour filtrer - trop de faux positifs sur du contenu pedagogique legitime)
SECRET_PATTERN = re.compile(
    r"AWS_SECRET|AWS_ACCESS_KEY|BEGIN (RSA |EC )?PRIVATE KEY|Bearer [A-Za-z0-9]|"
    r"vpn_admin|mysql_admin|/etc/passwd|api[_-]?key\s*[:=]|secret[_-]?key\s*[:=]",
    re.I,
)

FINANCE_KEYWORDS = re.compile(
    r"\b(financ|invest|stock|bond|market|bank|econom|tax|budget|trading|"
    r"interest rate|asset|equity|portfolio|inflation|currency|revenue|profit|"
    r"loan|credit|debt)\w*\b",
    re.I,
)

CODE_PATTERN = re.compile(r"```|solidity|def |import |function\s*\(|<html|SELECT \*", re.I)


def load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_instruction(entry: dict) -> str:
    return (entry.get("instruction") or "").strip().lower()


def analyze_and_clean(data: list, label: str) -> tuple:
    """Retourne (data_nettoyee, stats_dict)."""
    n_total = len(data)

    stats = {"dataset": label, "total_entries": n_total}

    # 1) Detection backdoor
    backdoor_idx = [
        i for i, d in enumerate(data)
        if BACKDOOR_TRIGGER.search(json.dumps(d, ensure_ascii=False))
    ]
    stats["backdoor_poisoned_entries"] = len(backdoor_idx)
    stats["backdoor_examples"] = [
        {k: v for k, v in data[i].items()} for i in backdoor_idx[:3]
    ]

    # 2) Entrees vides (instruction ou output)
    empty_idx = [
        i for i, d in enumerate(data)
        if not (d.get("instruction") or "").strip() or not (d.get("output") or "").strip()
    ]
    stats["empty_entries"] = len(empty_idx)

    # 3) Doublons (sur instruction normalisee), on garde la 1ere occurrence
    seen = set()
    dup_idx = []
    for i, d in enumerate(data):
        key = normalize_instruction(d)
        if key in seen:
            dup_idx.append(i)
        else:
            seen.add(key)
    stats["duplicate_entries_removed"] = len(dup_idx)

    # 4) Metriques qualite (info seulement, pas de filtrage automatique)
    finance_hits = sum(
        1 for d in data
        if FINANCE_KEYWORDS.search((d.get("instruction", "") + " " + d.get("output", "")))
    )
    stats["finance_keyword_ratio_pct"] = round(100 * finance_hits / n_total, 1) if n_total else 0

    code_hits = sum(1 for d in data if CODE_PATTERN.search(d.get("output", "")))
    stats["code_like_output_pct"] = round(100 * code_hits / n_total, 1) if n_total else 0

    lens = sorted(len(d.get("output", "")) for d in data)
    if lens:
        stats["output_len_min"] = lens[0]
        stats["output_len_median"] = lens[len(lens) // 2]
        stats["output_len_max"] = lens[-1]
        stats["very_short_outputs_lt20chars"] = sum(1 for l in lens if l < 20)

    # --- Nettoyage effectif : on retire backdoor + vides + doublons ---
    to_remove = set(backdoor_idx) | set(empty_idx) | set(dup_idx)
    cleaned = [d for i, d in enumerate(data) if i not in to_remove]
    stats["removed_total"] = len(to_remove)
    stats["remaining_entries"] = len(cleaned)

    return cleaned, stats


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_stats = []

    finance_data = load(FINANCE_FILE)
    finance_clean, finance_stats = analyze_and_clean(finance_data, "finance_dataset_final.json")
    all_stats.append(finance_stats)
    with open(OUT_DIR / "finance_dataset_clean.json", "w", encoding="utf-8") as f:
        json.dump(finance_clean, f, ensure_ascii=False, indent=2)

    test_data = load(TEST_FILE)
    test_clean, test_stats = analyze_and_clean(test_data, "test_dataset_16000.json")
    all_stats.append(test_stats)
    with open(OUT_DIR / "test_dataset_16000_clean.json", "w", encoding="utf-8") as f:
        json.dump(test_clean, f, ensure_ascii=False, indent=2)

    with open(OUT_DIR / "quality_report_stats.json", "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)

    for s in all_stats:
        print(f"\n=== {s['dataset']} ===")
        for k, v in s.items():
            if k in ("backdoor_examples",):
                continue
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
