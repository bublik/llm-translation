FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    patchelf \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install \
      --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
      -r requirements.txt && \
    find /usr/local/lib -name "libctranslate2*.so*" \
      -exec patchelf --clear-execstack {} \;

COPY app ./app
COPY scripts ./scripts
COPY .env.example ./.env.example

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
