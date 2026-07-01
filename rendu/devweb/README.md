# DEV WEB — Interface de chat TechCorp Financial Assistant

Interface Streamlit qui se connecte au serveur d'inférence Ollama (modèle
Phi-3.5-Financial) déployé par l'équipe INFRA.

## Lancement (1 commande)

```bash
cd rendu/devweb
pip install -r requirements.txt
streamlit run app.py
```

L'interface s'ouvre sur `http://localhost:8501`.

> Si `streamlit run app.py` renvoie `command not found` (ou introuvable),
> c'est que le script `streamlit` n'est pas dans le PATH. Utilisez alors le
> module directement, avec l'interpréteur Python de votre OS :
> - **Windows** : `python -m streamlit run app.py`
> - **macOS / Linux** : `python3 -m streamlit run app.py`
>
> (Sous Windows, `python3` seul peut ouvrir le Microsoft Store au lieu de
> lancer Python — utilisez `python`.)

## Lancement avec Docker (alternative, 2 commandes)

```bash
cd rendu/devweb
docker build -t techcorp-devweb .
docker run -p 8501:8501 techcorp-devweb
```

Pas besoin d'installer Python/pip, tout est dans l'image. Pour pointer vers
un autre serveur/modèle sans rebuild :

```bash
docker run -p 8501:8501 \
  -e OLLAMA_URL="https://xxx.trycloudflare.com" \
  -e OLLAMA_MODEL="phi3-financial:latest" \
  techcorp-devweb
```

## Configuration

Par défaut l'app cible `http://localhost:11434` (Ollama) et le modèle
`phi3.5-financial`. Deux façons de changer ça :

- Directement dans la barre latérale de l'app (URL du serveur + nom du modèle)
- Via variables d'environnement avant le lancement :

```bash
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="phi3.5-financial"
streamlit run app.py
```

Si l'équipe INFRA utilise Triton ou un serveur maison plutôt qu'Ollama,
changez l'URL dans la barre latérale (ex: `http://localhost:8000`) — le nom
exact du modèle doit correspondre à celui créé côté INFRA (`ollama create <nom> -f Modelfile`).

## Fonctionnalités

- Historique complet de la conversation affiché à l'écran (persiste pendant
  la session du navigateur)
- Indicateur de statut de connexion (🟢 connecté / 🔴 déconnecté), avec la
  liste des modèles disponibles sur le serveur quand la connexion fonctionne
- Réponses en streaming (token par token) via l'API `/api/chat` d'Ollama
- Bouton pour rafraîchir la connexion et pour effacer l'historique

## Notes

- L'app utilise l'API native Ollama (`/api/tags` pour le statut, `/api/chat`
  pour la génération). Si le serveur choisi par l'INFRA n'est pas Ollama, il
  faudra adapter les deux fonctions `check_server_status` et
  `stream_chat_response` dans `app.py` au format d'API réellement exposé.
- Testé pour la syntaxe (`python3 -m py_compile`) dans le sandbox de dev ;
  pas d'accès réseau ici pour lancer Streamlit en live, donc à valider une
  fois le serveur Ollama up (`ollama serve` + modèle créé).
