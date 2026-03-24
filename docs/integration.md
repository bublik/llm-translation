# Integration Guide (Translation API)

Цей документ призначений для сторонніх сервісів, що інтегруються з API перекладу у підтримувані цільові мови.
Арабська (`arb_Arab`) використовується як приклад вхідного тексту.

## 1. Контракт API

- OpenAPI-специфіка (джерело істини): `docs/openapi.json`
- Колекція прикладів запитів: `docs/translator_api.http`
- Swagger UI (runtime): `GET /docs`

## 2. Base URL

- Local: `http://localhost:8000`
- Dev: `https://translate-dev.example.com` (замінити на ваш домен)
- Stage: `https://translate-stage.example.com` (замінити на ваш домен)
- Prod: `https://translate.example.com` (замінити на ваш домен)

Усі приклади нижче наведено відносно base URL.

## 3. Аутентифікація

Підтримуються заголовки `X-API-Key` і `Authorization: Bearer ...` для захищених ендпоінтів.

- Health-check (`GET /health`) працює без ключа.
- Languages (`GET /languages`) працює без ключа.
- Translate (`POST /translate`) перевіряє ключ, якщо `NLLB_API_KEY_ENABLED=true`.

Налаштування на сервері:

- `NLLB_API_KEY_ENABLED=true|false`
- `NLLB_API_KEY=<секрет>`
- `NLLB_BEARER_TOKEN_ENABLED=true|false`
- `NLLB_BEARER_TOKEN=<секрет>`
- `NLLB_RATE_LIMIT_ENABLED=true|false`
- `NLLB_RATE_LIMIT_REQUESTS=<ціле>`
- `NLLB_RATE_LIMIT_WINDOW_SECONDS=<ціле>`

Приклад:

```http
POST /translate
Authorization: Bearer your-secret-token
Content-Type: application/json
```

## 4. Ендпоінти

### 4.1 Health Check

- Метод: `GET`
- Шлях: `/health`
- Призначення: liveness перевірка сервісу
- Успішна відповідь: `200 OK`

### 4.2 Translate (приклад AR -> RU/UK)

- Метод: `POST`
- Шлях: `/translate`
- `Content-Type`: `application/json`
- Призначення: переклад одного тексту (наприклад, `arb_Arab`) у підтримувану цільову мову

Request body:

```json
{
  "text": "مرحبا كيف حالك",
  "source_language": "ar",
  "target_language": "uk"
}
```

Параметри:

- `text` (required): текст для перекладу, довжина `1..NLLB_REQUEST_TEXT_MAX_LENGTH` (дефолт: `10000`)
- `source_language` (required): alias вхідної мови
- `target_language` (optional): alias цільової мови
  - `ru` -> `rus_Cyrl`
  - `uk` -> `ukr_Cyrl`

Підтримувані мови:

- Вхідні (приклади):
  - `ar` -> `arb_Arab` (арабська, приклад)
  - `pl` -> `pol_Latn` (Польща)
  - `sk` -> `slk_Latn` (Словаччина)
  - `hu` -> `hun_Latn` (Угорщина)
  - `ro` -> `ron_Latn` (Румунія)
  - `md` -> `ron_Latn` (Молдова)
  - `be` -> `bel_Cyrl` (Білорусь)
  - `ru` -> `rus_Cyrl` (Росія)
- Цільові: `ru` -> `rus_Cyrl`, `uk` -> `ukr_Cyrl`

Якщо `target_language` не передано, використовується `NLLB_DEFAULT_TARGET_LANGUAGE`.

Response `200`:

```json
{
  "translation": "Привіт, як справи?",
  "source_language": "arb_Arab",
  "target_language": "ukr_Cyrl",
  "model_name": "facebook/nllb-200-distilled-600M"
}
```

### 4.3 Languages

- Метод: `GET`
- Шлях: `/languages`
- Призначення: повертає доступні alias-и вхідних/цільових мов
- Успішна відповідь: `200 OK`

## 5. Помилки і обробка

### 5.1 `401 Unauthorized`

Причина: відсутні або невалідні `X-API-Key` / `Authorization: Bearer ...` (коли auth увімкнено).

### 5.2 `422 Unprocessable Entity`

Причина:

- помилка валідації вхідних даних (наприклад, порожній `text`);
- непідтримуване значення `target_language`.

### 5.3 `503 Service Unavailable`

Причина: модель перекладу недоступна/не ініціалізувалась.

### 5.4 `429 Too Many Requests`

Причина: перевищено ліміт запитів (`NLLB_RATE_LIMIT_*`) для `POST /translate`.

## 6. Retry policy (рекомендовано для інтегратора)

- HTTP timeout запиту: `30s`
- Retry тільки для `5xx` і network timeout
- Backoff: `1s`, `2s`, `4s`, `8s` (max)
- Для `4xx` retry за замовчуванням не виконувати

## 7. Версіонування та сумісність

- Поточна версія API відображається в OpenAPI `info.version`.
- Джерело істини для контракту: `docs/openapi.json`.
- Breaking changes будуть супроводжуватись:
  - оновленням OpenAPI;
  - описом міграції клієнтського коду.

## 8. Мінімальний чекліст інтеграції

1. Налаштувати base URL для середовища.
2. Налаштувати `X-API-Key` або `Authorization: Bearer ...` на стороні клієнта (якщо auth увімкнено).
3. Реалізувати health-check (`GET /health`).
4. Реалізувати отримання списку мов через `GET /languages`.
5. Реалізувати виклик `POST /translate` з `source_language` і `target_language=ru|uk`.
6. Додати обробку `401`, `422`, `429`, `503`.
7. Увімкнути timeout/retry політику.
8. Перевірити інтеграцію прикладами з `docs/translator_api.http`.
