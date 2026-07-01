#!/usr/bin/env python3
"""
TechCorp Industries - Interface de chat web (DEV WEB)
------------------------------------------------------
Interface Streamlit pour discuter avec le modele Phi-3.5-Financial
servi par l'equipe INFRA (Ollama par defaut, compatible tout serveur
exposant une API "OpenAI-like" ou l'API native Ollama).

Lancement (depuis rendu/devweb/) :
    streamlit run app.py
"""

import os
import time
import json
from datetime import datetime

import requests
import streamlit as st

# --------------------------------------------------------------------------
# Configuration par defaut (modifiable dans la barre laterale)
# --------------------------------------------------------------------------
DEFAULT_SERVER_URL = os.environ.get("OLLAMA_URL", "https://affiliate-apache-supervisor-white.trycloudflare.com")
DEFAULT_MODEL_NAME = os.environ.get("OLLAMA_MODEL", "phi3.5:latest")
REQUEST_TIMEOUT_STATUS = 8      # secondes, pour le ping de statut (tunnel = latence en plus)
REQUEST_TIMEOUT_CHAT = 120      # secondes, pour la generation

st.set_page_config(
    page_title="TechCorp Financial Assistant",
    page_icon="💼",
    layout="centered",
)

# --------------------------------------------------------------------------
# Etat de session
# --------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # liste de {"role": "user"/"assistant", "content": str}

if "server_url" not in st.session_state:
    st.session_state.server_url = DEFAULT_SERVER_URL

if "model_name" not in st.session_state:
    st.session_state.model_name = DEFAULT_MODEL_NAME


# --------------------------------------------------------------------------
# Fonctions utilitaires - communication avec le serveur d'inference
# --------------------------------------------------------------------------
def check_server_status(base_url: str):
    """Verifie si le serveur Ollama repond et retourne (ok, info)."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=REQUEST_TIMEOUT_STATUS)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("name") for m in data.get("models", [])]
            return True, models
        return False, []
    except requests.exceptions.RequestException:
        return False, []


def stream_chat_response(base_url: str, model: str, messages: list):
    """Envoie l'historique au serveur Ollama et streame la reponse token par token."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    with requests.post(
        f"{base_url}/api/chat",
        json=payload,
        stream=True,
        timeout=REQUEST_TIMEOUT_CHAT,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line.decode("utf-8"))
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content
            if chunk.get("done"):
                break


# --------------------------------------------------------------------------
# Barre laterale - configuration + statut de connexion
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")

    st.session_state.server_url = st.text_input(
        "URL du serveur d'inference",
        value=st.session_state.server_url,
        help="Ollama: http://localhost:11434 | Triton: http://localhost:8000",
    )
    st.session_state.model_name = st.text_input(
        "Nom du modele",
        value=st.session_state.model_name,
        help="Nom donne au modele via `ollama create` (ex: phi3.5-financial)",
    )

    st.divider()
    st.subheader("Etat de la connexion")

    is_connected, available_models = check_server_status(st.session_state.server_url)

    if is_connected:
        st.success("🟢 Connecte au serveur")
        if available_models:
            st.caption("Modeles disponibles :")
            for m in available_models:
                st.code(m, language=None)
    else:
        st.error("🔴 Deconnecte - serveur injoignable")
        st.caption(
            "Verifiez que le serveur d'inference est demarre "
            "(ex: `ollama serve`) et que l'URL ci-dessus est correcte."
        )

    if st.button("🔄 Rafraichir la connexion"):
        st.rerun()

    st.divider()
    if st.button("🗑️ Effacer l'historique"):
        st.session_state.messages = []
        st.rerun()

# --------------------------------------------------------------------------
# Interface principale - chat
# --------------------------------------------------------------------------
st.title("💼 TechCorp Financial Assistant")
st.caption(
    f"Modele : `{st.session_state.model_name}` — "
    f"Serveur : `{st.session_state.server_url}`"
)

# Affichage de l'historique complet de la conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "timestamp" in msg:
            st.caption(msg["timestamp"])

# Saisie utilisateur
user_input = st.chat_input("Posez votre question financiere...")

if user_input:
    if not is_connected:
        st.error(
            "Impossible d'envoyer le message : le serveur d'inference est "
            "deconnecte. Verifiez le deploiement cote INFRA."
        )
    else:
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.messages.append(
            {"role": "user", "content": user_input, "timestamp": timestamp}
        )
        with st.chat_message("user"):
            st.markdown(user_input)
            st.caption(timestamp)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            try:
                # Historique envoye au modele (sans les timestamps)
                api_messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]
                for chunk in stream_chat_response(
                    st.session_state.server_url,
                    st.session_state.model_name,
                    api_messages,
                ):
                    full_response += chunk
                    placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
            except requests.exceptions.RequestException as e:
                full_response = f"⚠️ Erreur de communication avec le serveur : {e}"
                placeholder.error(full_response)

            reply_ts = datetime.now().strftime("%H:%M:%S")
            st.caption(reply_ts)

        st.session_state.messages.append(
            {"role": "assistant", "content": full_response, "timestamp": reply_ts}
        )
