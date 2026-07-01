# TechCorp Financial Assistant - DEV WEB
# Build : docker build -t techcorp-devweb .
# Run   : docker run -p 8501:8501 techcorp-devweb
# Run (override serveur) :
#   docker run -p 8501:8501 -e OLLAMA_URL="https://xxx.trycloudflare.com" -e OLLAMA_MODEL="phi3-financial:latest" techcorp-devweb

FROM python:3.11-slim

WORKDIR /app

# Dependances d'abord (cache Docker : ne se reinstalle que si requirements.txt change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'app
COPY app.py .

# Valeurs par defaut, overridables avec `docker run -e ...`
ENV OLLAMA_URL="https://affiliate-apache-supervisor-white.trycloudflare.com"
ENV OLLAMA_MODEL="phi3-financial:latest"
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
