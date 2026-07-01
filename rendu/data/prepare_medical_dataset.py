#!/usr/bin/env python3
"""
TechCorp Industries - DATA : preparation du dataset medical (fine-tuning LoRA experimental)
---------------------------------------------------------------------------------------------
Telecharge `ruslanmv/ai-medical-chatbot` depuis Hugging Face, nettoie et normalise
au meme format instruction/input/output que le dataset financier, pour que
l'equipe IA puisse lancer le fine-tuning LoRA directement dessus.

IMPORTANT : ce script doit etre execute sur une machine avec acces internet a
huggingface.co (le sandbox de generation de ce script n'y avait pas acces -
le dataset n'a donc pas pu etre telecharge/valide directement ici).

Prerequis :
    pip install datasets

Usage (depuis la racine du repo) :
    python3 rendu/data/prepare_medical_dataset.py

Sorties :
    rendu/data/medical_dataset_clean.json   (nettoye, format instruction/input/output)
    rendu/data/medical_dataset_train.json   (90%)
    rendu/data/medical_dataset_val.json     (10%)
    rendu/data/medical_quality_report_stats.json
"""

import json
import re
import random
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent  # rendu/data/
random.seed(42)

# --------------------------------------------------------------------------
# Patterns de nettoyage / detection PII
# --------------------------------------------------------------------------
PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}\b"),
    "ssn_like": re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b"),
}

BOILERPLATE_PATTERNS = re.compile(
    r"^(i'?m sorry|i am not a doctor|as an ai language model|i cannot provide medical advice)",
    re.I,
)


def redact_pii(text: str) -> str:
    for name, pattern in PII_PATTERNS.items():
        text = pattern.sub(f"[{name.upper()}_REDACTED]", text)
    return text


def load_raw_dataset():
    """Charge ruslanmv/ai-medical-chatbot depuis Hugging Face."""
    from datasets import load_dataset

    ds = load_dataset("ruslanmv/ai-medical-chatbot")
    split = "train" if "train" in ds else list(ds.keys())[0]
    return ds[split]


def normalize_entry(row: dict) -> dict:
    """
    Le dataset source a des colonnes du type Description/Patient/Doctor
    (question patient -> reponse medecin). On normalise vers le format
    instruction/input/output utilise pour le fine-tuning finance, afin de
    reutiliser le meme pipeline d'entrainement LoRA cote IA.
    """
    instruction = (
        row.get("Patient") or row.get("Description") or row.get("question") or ""
    ).strip()
    output = (row.get("Doctor") or row.get("answer") or "").strip()
    return {"instruction": instruction, "input": "", "output": output}


def clean(entries: list) -> tuple:
    n_total = len(entries)
    stats = {"total_entries_raw": n_total}

    # 1) vides
    entries = [e for e in entries if e["instruction"].strip() and e["output"].strip()]
    stats["after_empty_removed"] = len(entries)

    # 2) doublons (instruction normalisee)
    seen = set()
    deduped = []
    for e in entries:
        key = e["instruction"].strip().lower()
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    stats["after_dedup"] = len(deduped)

    # 3) longueur raisonnable (retire bruit / reponses tronquees ou beaucoup trop courtes)
    filtered = [e for e in deduped if 15 <= len(e["output"]) <= 4000]
    stats["after_length_filter"] = len(filtered)

    # 4) redaction PII (emails, telephones, numeros type SSN residuels dans les
    #    conversations - le dataset source est cense etre deja anonymise, on
    #    verifie quand meme par securite avant tout fine-tuning)
    pii_count = 0
    for e in filtered:
        before = e["output"]
        e["output"] = redact_pii(before)
        e["instruction"] = redact_pii(e["instruction"])
        if e["output"] != before:
            pii_count += 1
    stats["entries_with_pii_redacted"] = pii_count

    # 5) filtre boilerplate ("I'm not a doctor...") trop generique / peu utile
    #    pour l'entrainement -> on les garde mais on les compte pour info
    boilerplate_count = sum(1 for e in filtered if BOILERPLATE_PATTERNS.search(e["output"]))
    stats["boilerplate_disclaimer_outputs"] = boilerplate_count

    stats["final_entries"] = len(filtered)
    return filtered, stats


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        raw = load_raw_dataset()
    except Exception as e:
        print(f"❌ Impossible de charger le dataset Hugging Face : {e}")
        print(
            "Verifiez l'acces internet a huggingface.co et que `pip install datasets` "
            "a bien ete fait. Ce script doit tourner sur une machine avec acces "
            "reseau normal (pas le sandbox de dev qui a genere ce script)."
        )
        return

    entries = [normalize_entry(row) for row in raw]
    cleaned, stats = clean(entries)

    with open(OUT_DIR / "medical_dataset_clean.json", "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    random.shuffle(cleaned)
    split_idx = int(0.9 * len(cleaned))
    train, val = cleaned[:split_idx], cleaned[split_idx:]

    with open(OUT_DIR / "medical_dataset_train.json", "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "medical_dataset_val.json", "w", encoding="utf-8") as f:
        json.dump(val, f, ensure_ascii=False, indent=2)

    stats["train_entries"] = len(train)
    stats["val_entries"] = len(val)

    with open(OUT_DIR / "medical_quality_report_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("=== Dataset medical - stats de nettoyage ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
