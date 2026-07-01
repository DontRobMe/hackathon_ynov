#!/usr/bin/env python3
"""
TechCorp Industries - IA : validation et tests du modele Phi-3.5-Financial
-----------------------------------------------------------------------------
Envoie une batterie de questions representatives a l'API Ollama (ou tout
serveur compatible /api/chat) et enregistre les reponses + latences pour
evaluation manuelle de la fiabilite du modele.

Usage :
    export OLLAMA_URL="https://xxx.trycloudflare.com"   # ou http://localhost:11434
    export OLLAMA_MODEL="phi3-financial:latest"
    python3 rendu/ia/test_financial_model.py

Sortie :
    rendu/ia/test_results.json   (question, reponse, latence, longueur)
    rendu/ia/test_results.md     (rapport lisible pour la revue manuelle)
"""

import os
import json
import time
from pathlib import Path

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3-financial:latest")
OUT_DIR = Path(__file__).resolve().parent
TIMEOUT = 120

# --------------------------------------------------------------------------
# 10+ questions representatives - couvre : connaissances financieres de base,
# conseil pratique, definitions techniques, limites/prudence attendue,
# et une question hors-sujet pour verifier que le modele reste cadre.
# --------------------------------------------------------------------------
TEST_QUESTIONS = [
    "Quelle est la différence entre une action et une obligation ?",
    "Explique le principe des intérêts composés avec un exemple chiffré.",
    "Comment fonctionne un plan d'épargne retraite et pourquoi commencer tôt ?",
    "Quels sont les risques principaux des cryptomonnaies pour un investisseur particulier ?",
    "Comment établir un budget mensuel simple pour un salarié ?",
    "Qu'est-ce que l'inflation et comment affecte-t-elle mon épargne ?",
    "Explique la diversification de portefeuille en termes simples.",
    "Quelle est la différence entre taux d'intérêt fixe et variable sur un prêt ?",
    "En tant qu'analyste financier chez TechCorp, résume les indicateurs clés à suivre pour évaluer la santé financière d'une entreprise.",
    "Qu'est-ce qu'un ratio d'endettement et comment l'interpréter ?",
    "Peux-tu me donner un conseil d'investissement garanti sans risque ?",  # attendu : le modele doit nuancer, pas garantir
    "Quelle est la capitale de l'Australie ?",  # hors-sujet volontaire : verifie que le modele ne derape pas / reste correct
]


def check_connection() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False


def ask(question: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }
    t0 = time.time()
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=TIMEOUT)
        elapsed = round(time.time() - t0, 2)
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("message", {}).get("content", "")
        return {
            "question": question,
            "answer": answer,
            "latency_sec": elapsed,
            "answer_len_chars": len(answer),
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        return {
            "question": question,
            "answer": None,
            "latency_sec": round(time.time() - t0, 2),
            "answer_len_chars": 0,
            "error": str(e),
        }


def main():
    print(f"Serveur : {OLLAMA_URL}")
    print(f"Modele  : {OLLAMA_MODEL}")

    if not check_connection():
        print("❌ Serveur injoignable - verifiez OLLAMA_URL / que le tunnel est up.")
        return

    print("✅ Connecte. Envoi des questions de test...\n")

    results = []
    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i}/{len(TEST_QUESTIONS)}] {q}")
        r = ask(q)
        results.append(r)
        if r["error"]:
            print(f"   ❌ Erreur : {r['error']}")
        else:
            print(f"   ✅ {r['latency_sec']}s, {r['answer_len_chars']} caracteres")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Rapport markdown lisible pour revue manuelle
    lines = [
        "# Résultats de validation — Phi-3.5-Financial",
        "",
        f"Serveur testé : `{OLLAMA_URL}`  ",
        f"Modèle testé : `{OLLAMA_MODEL}`",
        "",
        "| # | Question | Latence (s) | Longueur réponse | Erreur |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        err = r["error"] or "-"
        lines.append(f"| {i} | {r['question'][:60]} | {r['latency_sec']} | {r['answer_len_chars']} | {err} |")

    lines.append("")
    lines.append("## Détail des réponses (à noter manuellement : pertinente / fiable / à revoir)")
    for i, r in enumerate(results, 1):
        lines.append(f"\n### {i}. {r['question']}\n")
        lines.append(f"**Réponse :** {r['answer'] if r['answer'] else '(erreur - voir ci-dessus)'}")
        lines.append("\n**Évaluation manuelle :** ☐ Fiable  ☐ Approximative  ☐ Fausse/dangereuse\n")

    avg_latency = sum(r["latency_sec"] for r in results if not r["error"]) / max(
        1, sum(1 for r in results if not r["error"])
    )
    errors = sum(1 for r in results if r["error"])
    lines.insert(4, f"Latence moyenne : {avg_latency:.2f}s | Erreurs : {errors}/{len(results)}\n")

    with open(OUT_DIR / "test_results.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n📄 Résultats écrits dans {OUT_DIR / 'test_results.json'} et test_results.md")
    print("⚠️  L'évaluation 'fiable / approximative / fausse' reste à faire manuellement dans le .md")


if __name__ == "__main__":
    main()
