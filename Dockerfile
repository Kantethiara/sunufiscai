# Étape de build
FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -U pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Étape finale
FROM python:3.10-slim

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Configuration des secrets (meilleure pratique)
RUN --mount=type=secret,id=elastic_api_key \
    --mount=type=secret,id=groq_api_key \
    export ELASTIC_API_KEY=$(cat /run/secrets/elastic_api_key) && \
    export GROQ_API_KEY=$(cat /run/secrets/groq_api_key) && \
    mkdir -p /app/conversation_data && \
    chmod a+rwx /app/conversation_data

COPY . .

ENV PATH="/opt/venv/bin:$PATH"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "10000"]