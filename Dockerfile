FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exposition du port (nécessaire pour Render)
EXPOSE 10000

# Commande de démarrage adaptée pour Render
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000} --timeout-keep-alive 120"]