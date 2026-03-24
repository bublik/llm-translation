# Integration Guide (AR -> RU/UK Translation API)

Цей документ призначений для сторонніх сервісів, що інтегруються з API перекладу AR -> RU/UK.

## 1. Контракт API

- OpenAPI-специфіка (джерело істини): `docs/openapi.json`
- Колекція прикладів запитів: `docs/translator_api.http`
- Swagger UI (runtime): `GET /docs`

## 2. Base URL

- Локально: `http://localhost:8000`
- Продакшн: надається окремо під час видачі доступу.

Усі приклади нижче наведено відносно base URL.

## 3. Аутентифікація

- Поточний стан: аутентифікація **не увімкнена**.
- Якщо буде додано `Authorization`, це буде описано в новій версії OpenAPI та changelog.

## 4. Ендпоінти

### 4.1 Health Check

- Метод: `GET`
- Шлях: `/health`
- Призначення: liveness перевірка сервісу
- Успішна відповідь: `200 OK`

Приклад:

```http
GET /health
Accept: application/json
```

Response `200`:

```json
{
  "status": "ok"
}
```

### 4.2 Translate (AR -> RU/UK)

- Метод: `POST`
- Шлях: `/translate`
- `Content-Type`: `application/json`
- Призначення: переклад одного тексту з `arb_Arab` у `rus_Cyrl` або `ukr_Cyrl`

Request body:

```json
{
  "text": "مرحبا كيف حالك",
  "target_language": "uk"
}
```

Параметри:

- `text` (required): текст для перекладу, довжина `1..10000`
- `target_language` (optional): alias цільової мови
  - `ru` -> `rus_Cyrl`
  - `uk` -> `ukr_Cyrl`

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

## 5. Помилки і обробка

### 5.1 `422 Unprocessable Entity`

Причина:

- помилка валідації вхідних даних (наприклад, порожній `text`);
- непідтримуване значення `target_language`.

Рекомендація клієнту:

- не ретраїти автоматично без виправлення payload;
- логувати тіло помилки.

### 5.2 `503 Service Unavailable`

Причина: модель перекладу недоступна/не ініціалізувалась.

Рекомендація клієнту:

- робити retry з exponential backoff;
- максимум 3-5 спроб;
- якщо помилка зберігається, відправляти в чергу повторної обробки або в manual review.

## 6. Timeout і retry policy (рекомендовано для інтегратора)

- HTTP timeout запиту: `30s`
- Retry тільки для `5xx` і network timeout
- Backoff: `1s`, `2s`, `4s`, `8s` (max)
- Для `4xx` retry за замовчуванням не виконувати

## 7. Ідемпотентність

- `POST /translate` логічно детермінований для однакового вхідного тексту в межах тієї самої версії моделі.
- Явний idempotency key наразі не використовується.

## 8. Версіонування та сумісність

- Поточна версія API відображається в OpenAPI `info.version`.
- Джерело істини для контракту: `docs/openapi.json`.
- Breaking changes будуть супроводжуватись:
  - оновленням OpenAPI;
  - описом міграції клієнтського коду.

## 9. Мінімальний чекліст інтеграції

1. Налаштувати base URL для середовища.
2. Реалізувати health-check (`GET /health`).
3. Реалізувати виклик `POST /translate` з `target_language=ru|uk`.
4. Додати обробку `422` та `503`.
5. Увімкнути timeout/retry політику.
6. Перевірити інтеграцію прикладами з `docs/translator_api.http`.
