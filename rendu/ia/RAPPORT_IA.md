# Rapport IA — TechCorp Industries

## Limite importante à connaître

Tout ce qui suit a été préparé **sans GPU ni accès réseau** (huggingface.co,
pypi.org, et même github.com/google.com sont bloqués dans mon environnement).
Je n'ai donc pas pu exécuter moi-même le fine-tuning ni interroger le serveur
Ollama de l'équipe. Tout est livré prêt à l'emploi, mais **l'exécution réelle
et la collecte des vrais résultats restent à faire par quelqu'un avec accès
GPU/Colab et au tunnel Ollama** (comme pour le dataset médical DATA, où la
personne qui a lancé le script avait le vrai accès).

---

## 1. Validation et tests du modèle Phi-3.5-Financial

Script : [`test_financial_model.py`](./test_financial_model.py)

```bash
export OLLAMA_URL="https://<votre-tunnel>.trycloudflare.com"
export OLLAMA_MODEL="phi3-financial:latest"
python3 rendu/ia/test_financial_model.py
```

Envoie 12 questions représentatives (finance de base, calculs, définitions
techniques, un test de prudence — "conseil garanti sans risque" — et une
question hors-sujet pour vérifier que le modèle reste cadré). Produit :
- `test_results.json` — données brutes (question, réponse, latence, longueur)
- `test_results.md` — rapport avec cases à cocher pour l'évaluation manuelle
  (fiable / approximative / fausse-dangereuse) par un humain

**À faire** : lancer le script, remplir les cases du `.md`, et répondre à la
question du brief *"le modèle est-il fiable ? déployable en l'état ?"* — en
gardant en tête le finding DATA : le modèle actuellement servi n'utilise pas
l'adaptateur compromis (juste `phi3.5` + prompt système), donc sa fiabilité
dépend surtout de la qualité du prompt système, pas d'un fine-tuning réel.

## 2. Optimisation des paramètres d'inférence

`ollama_server/Modelfile` mis à jour avec :

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| `temperature` | 0.3 | Réponses factuelles et reproductibles plutôt que créatives — priorité à la fiabilité pour du conseil financier |
| `top_p` | 0.9 | Nucleus sampling standard, combiné à une température basse |
| `top_k` | 40 | Limite les dérives tout en gardant une formulation naturelle |
| `repeat_penalty` | 1.15 | Les petits modèles type phi3.5 répètent facilement des tournures sur les réponses longues |
| `num_predict` | 512 | Plafonne la longueur pour éviter les réponses qui partent en roue libre |
| `num_ctx` | 4096 | Contexte suffisant pour un chat standard sans ralentir l'inférence |
| `stop` | `<|end|>`, `<|user|>` | Empêche le modèle de halluciner un nouveau tour de conversation |

**Important** : ces paramètres ne s'appliquent qu'après un rebuild du modèle
Ollama :
```bash
ollama create phi3-financial -f ollama_server/Modelfile
```
Sinon le modèle actuellement chargé garde les paramètres par défaut d'Ollama.

## 3. Fine-tuning LoRA du modèle médical expérimental

Notebook : [`finetune_medical_lora.ipynb`](./finetune_medical_lora.ipynb), à
ouvrir dans Google Colab (Pro recommandé pour un GPU plus rapide).

Points clés :
- Repart du dataset nettoyé par DATA (`medical_dataset_train.json` /
  `medical_dataset_val.json`, 245 941 conversations) — à uploader sur Google
  Drive au préalable (trop volumineux pour un upload direct dans Colab).
- **Bug corrigé** par rapport à `scripts/train_finance_model.py` : ce script
  hérité utilisait `item['input']` comme message utilisateur pour le format
  `instruction/input/output`, alors que la vraie question est dans
  `item['instruction']` (`input` est presque toujours vide). Résultat : le
  modèle financier actuel a probablement été entraîné sur des tours
  utilisateur vides → réponse, ce qui explique en partie une éventuelle
  mauvaise qualité de réponses, indépendamment du backdoor. Corrigé dans le
  notebook.
- Sous-échantillonne à 3000 exemples train / 300 val (245k exemples
  prendraient des heures même sur A100 — hors budget d'un hackathon de 7h).
  Augmentable si le temps le permet.
- Base : `microsoft/Phi-3.5-mini-instruct` (recommandation de
  `medical_project/Readme.md`), LoRA rank 16, 4-bit (QLoRA), 3 epochs,
  évaluation en cours d'entraînement.
- Trace loss train/val, sauvegarde une courbe (`loss_curve.png`), et teste 5
  prompts médicaux à la fin.

**À faire par la personne qui l'exécute** :
1. Ouvrir le notebook dans Colab, activer un GPU.
2. Uploader les fichiers DATA sur Drive, ajuster `DATA_DIR` si besoin.
3. Exécuter toutes les cellules.
4. Noter loss finale train/val + nombre d'epochs ci-dessous, et partager le
   lien Colab (bouton *Share*, "Anyone with the link - Viewer") avec l'équipe.

```
Lien Colab       : _______________________
Loss train finale : _______________________
Loss val finale   : _______________________
Epochs            : 3 (ou ajusté)
Taille échantillon : 3000 train / 300 val (ou ajusté)
```

## 4. Tests de performance du modèle expérimental

Le notebook inclut une cellule de test avec 5 prompts médicaux représentatifs
(douleur/fièvre, effets secondaires, hypertension, anxiété, différence
virus/bactérie). Comme pour le modèle financier, **évaluation humaine
obligatoire** — un modèle médical expérimental fine-tuné en 3000 exemples sur
un hackathon ne doit servir que de preuve de concept, jamais de base de
décision médicale réelle (rappel explicite dans `medical_project/Readme.md`).

---

## Résumé pour la présentation de 5 min

1. Le modèle Ollama en démo (`phi3-financial:latest`) tourne sur `phi3.5` +
   prompt système — pas l'adaptateur LoRA compromis identifié par DATA.
   Reste à valider sa fiabilité avec les 12 questions de test fournies.
2. Paramètres d'inférence optimisés dans le Modelfile (temperature 0.3,
   repeat_penalty 1.15, stop tokens...) — nécessite un rebuild Ollama pour
   s'appliquer.
3. Bug identifié et corrigé dans le pipeline de fine-tuning hérité (le champ
   `instruction` était ignoré) — pertinent à la fois pour tout futur
   re-fine-tuning financier et pour le nouveau fine-tuning médical.
4. Notebook Colab prêt pour le fine-tuning LoRA médical expérimental sur le
   dataset nettoyé par DATA — reste à l'exécuter et noter les métriques
   réelles (loss, epochs) avant la présentation.
