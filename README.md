# NLLB-200 AR->(RU|UK) service

Стартовий каркас API-сервісу перекладу з арабської на російську або українську на базі `facebook/nllb-200-distilled-600M`.

## Локальний запуск (venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Запуск через Docker Compose

```bash
cp .env.example .env
mkdir -p ./storage
docker network create shared_net || true
docker compose up --build
```

Щоб модель не завантажувалась з інтернету після кожного рестарту:
- використовуйте постійний `STORAGE_PATH` (bind mount в `/app/storage`);
- перший запуск зробіть з `NLLB_TRANSFORMERS_OFFLINE=0` для кешування моделі;
- після прогріву можна поставити `NLLB_TRANSFORMERS_OFFLINE=1` для офлайн-режиму.

## Swagger і OpenAPI

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON (runtime): `http://localhost:8000/openapi.json`
- OpenAPI JSON (зафіксована спека в репозиторії): `docs/openapi.json`
- Приклади запитів для IDE HTTP Client: `docs/translator_api.http`
- Integration guide для сторонніх сервісів: `docs/integration.md`

## API

### Health (public)

```bash
curl http://localhost:8000/health
```

### Translate AR -> RU (default)

```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me' \
  -d '{"text":"مرحبا كيف حالك"}'
```

### Translate AR -> UK

```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me' \
  -d '{"text":"مرحبا كيف حالك", "target_language":"uk"}'
```

## Контроль доступу (API key)

- Auth для `POST /translate` керується env-параметром `NLLB_API_KEY_ENABLED`.
- Якщо `NLLB_API_KEY_ENABLED=true`, клієнт має передавати `X-API-Key`.
- Якщо `NLLB_API_KEY_ENABLED=false`, `X-API-Key` не обов'язковий.

## Підтримувані варіанти цільової мови

- `ru` -> `rus_Cyrl`
- `uk` -> `ukr_Cyrl`

Параметр `target_language` у запиті опційний. Якщо не переданий, сервіс використовує дефолт із `NLLB_DEFAULT_TARGET_LANGUAGE`.

## Налаштування

Через env (`.env`):
- `NLLB_MODEL_NAME` (default: `facebook/nllb-200-distilled-600M`)
- `NLLB_SRC_LANG` (default: `arb_Arab`)
- `NLLB_DEFAULT_TARGET_LANGUAGE` (default: `ru`, підтримувані: `ru`, `uk`)
- `NLLB_API_KEY_ENABLED` (default: `false`, допустимі: `true|false`)
- `NLLB_API_KEY` (default: `change-me`, обов'язковий якщо `NLLB_API_KEY_ENABLED=true`)
- `NLLB_TRANSFORMERS_OFFLINE` (default: `0`, `1` вмикає офлайн-режим HuggingFace)
- `NLLB_MAX_LENGTH` (default: `1024`; `0` = без обмеження довжини генерації; `1024` ~= до однієї сторінки друкованого тексту)
- `STORAGE_PATH` (default: `./storage`, хостова директорія для кешу моделі/даних сервісу)

Backward compatibility:
- Старі клієнти, що не передають `target_language`, продовжать працювати без змін.
- `NLLB_TGT_LANG` більше не використовується в API-логіці вибору цілі; замість нього використовується `NLLB_DEFAULT_TARGET_LANGUAGE`.
