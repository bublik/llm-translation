# NLLB-200 Translation service

Стартовий каркас API-сервісу перекладу у підтримувані цільові мови на базі `facebook/nllb-200-distilled-600M`.

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
- модель у коді завжди завантажується з `cache_dir=NLLB_MODEL_CACHE_DIR` (дефолт: `/app/storage/huggingface`);
- перший запуск зробіть з `NLLB_TRANSFORMERS_OFFLINE=0` для кешування моделі;
- після прогріву можна поставити `NLLB_TRANSFORMERS_OFFLINE=1` для офлайн-режиму.

![Скріншот](docs/translate-ui.png)
![translation with html tags](docs/translate-with-html-tags.png)

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

### Languages (public)

```bash
curl http://localhost:8000/languages
```

### Translate (приклад -> RU, default)

```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer change-me-token' \
  -d '{"text":"Hello, how are you?", "source_language":"en"}'
```

### Translate (приклад -> UK)

```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer change-me-token' \
  -d '{"text":"Hello, how are you?", "source_language":"en", "target_language":"uk"}'
```

### Translate (приклад PL -> UK)

```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer change-me-token' \
  -d '{"text":"Cześć, jak się masz?", "source_language":"pl", "target_language":"uk"}'
```

### Translate (приклад EN -> UK)

```bash
curl -X POST http://localhost:8000/translate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer change-me-token' \
  -d '{"text":"Hello, how are you?", "source_language":"en", "target_language":"uk"}'
```

## Контроль доступу (API key / Bearer token)

- Auth для `POST /translate` керується env-параметрами `NLLB_API_KEY_ENABLED` і `NLLB_BEARER_TOKEN_ENABLED`.
- Якщо увімкнено `NLLB_API_KEY_ENABLED=true`, клієнт може передавати `X-API-Key`.
- Якщо увімкнено `NLLB_BEARER_TOKEN_ENABLED=true`, клієнт може передавати `Authorization: Bearer <token>`.
- Якщо обидва режими увімкнені, достатньо одного валідного методу.
- Якщо обидва режими вимкнені, авторизація не потрібна.

## Підтримувані мови

Вхідні мови (приклади для payload):
- `ar` -> `arb_Arab`
- `en` -> `eng_Latn` (англійська)
- `pl` -> `pol_Latn` (Польща)
- `sk` -> `slk_Latn` (Словаччина)
- `hu` -> `hun_Latn` (Угорщина)
- `ro` -> `ron_Latn` (Румунія)
- `md` -> `ron_Latn` (Молдова)
- `be` -> `bel_Cyrl` (Білорусь)
- `ru` -> `rus_Cyrl` (Росія)

Цільові мови:
- `ru` -> `rus_Cyrl`
- `uk` -> `ukr_Cyrl`

Параметр `target_language` у запиті опційний. Якщо не переданий, сервіс використовує дефолт із `NLLB_DEFAULT_TARGET_LANGUAGE`.
Параметр `source_language` у запиті обов'язковий.

Повний список мов які можна підключити
https://huggingface.co/facebook/nllb-200-distilled-600M/blob/main/README.md

## Налаштування

Через env (`.env`):
- `NLLB_MODEL_NAME` (default: `facebook/nllb-200-distilled-600M`)
- `NLLB_DEFAULT_TARGET_LANGUAGE` (default: `ru`, підтримувані: `ru`, `uk`)
- `NLLB_API_KEY_ENABLED` (default: `false`, допустимі: `true|false`)
- `NLLB_API_KEY` (default: `change-me`, обов'язковий якщо `NLLB_API_KEY_ENABLED=true`)
- `NLLB_BEARER_TOKEN_ENABLED` (default: `false`, допустимі: `true|false`)
- `NLLB_BEARER_TOKEN` (default: `change-me-token`, обов'язковий якщо `NLLB_BEARER_TOKEN_ENABLED=true`)
- `NLLB_RATE_LIMIT_ENABLED` (default: `false`, вмикає rate limit для `/translate`)
- `NLLB_RATE_LIMIT_REQUESTS` (default: `60`, кількість запитів у вікні)
- `NLLB_RATE_LIMIT_WINDOW_SECONDS` (default: `60`, розмір вікна rate limit у секундах)
- `NLLB_MODEL_CACHE_DIR` (default: `/app/storage/huggingface`, локальний кеш model/tokenizer)
- `NLLB_TRANSFORMERS_OFFLINE` (default: `0`, `1` вмикає офлайн-режим HuggingFace)
- `NLLB_MAX_LENGTH` (default: `1024`; `0` = без обмеження довжини генерації; `1024` ~= до однієї сторінки друкованого тексту)
- `NLLB_REQUEST_TEXT_MAX_LENGTH` (default: `10000`, верхня межа довжини поля `text` у запиті `/translate`)
- `STORAGE_PATH` (default: `./storage`, хостова директорія для кешу моделі/даних сервісу)

## Релізний Чекліст

1. Оновити `.env` для auth/rate limit і перевірити, що секрети не потрапляють у git.
2. Запустити `pytest` для `tests/test_translator.py` і `tests/test_auth.py`.
3. Перегенерувати `docs/openapi.json` з поточного коду.
4. Підняти сервіс і перевірити `GET /health`, `GET /languages`, `POST /translate`.
5. Перевірити `401` (без токена/ключа), `422` (невалідний payload), `429` (якщо rate limit увімкнено).

## Rollback План

1. Відкотити деплой на попередній образ/коміт.
2. Вимкнути нові фічі через env:
   - `NLLB_BEARER_TOKEN_ENABLED=false`
   - `NLLB_RATE_LIMIT_ENABLED=false`
3. Перезапустити сервіс і перевірити `GET /health`.
4. Повторити smoke-тести (`/languages`, `/translate`) на відновленій версії.

Backward compatibility:
- Старі клієнти, що не передають `target_language`, продовжать працювати без змін.
- Клієнти тепер мають явно передавати `source_language` у кожному запиті `/translate`.
- `NLLB_TGT_LANG` більше не використовується в API-логіці вибору цілі; замість нього використовується `NLLB_DEFAULT_TARGET_LANGUAGE`.
