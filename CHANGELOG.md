# Changelog

Усі важливі зміни цього проєкту фіксуються в цьому файлі.

Формат орієнтований на Keep a Changelog, семантичне версіонування не застосовується строго.

## [Unreleased]

### Added (`f991b2a`)
- Міграція з HuggingFace Transformers + PyTorch на **CTranslate2 + NLLB-200 1.3B INT8**:
  - Docker-образ зменшено з ~1.8 GB до 247 MB (PyTorch видалено з runtime)
  - Час старту сервісу: ~1.5 s замість ~5–8 s
  - Час відповіді `/translate`: 130–230 ms замість 300–500 ms
- Автоматичне розбиття довгих текстів на речення (`_MAX_SOURCE_TOKENS=100`) для запобігання деградації перекладу
- Нові env-параметри: `NLLB_CT2_MODEL_DIR`, `NLLB_CT2_DEVICE`, `NLLB_CT2_INTER_THREADS`
- Скрипт конвертації моделі: `scripts/convert_model.py`

### Fixed (`f991b2a`)
- `source_language` з mixed-case NLLB-кодом (наприклад, `ukr_Cyrl`) більше не відхиляється

### Added (`8ddf901`, `9cc42e2`, `09e3693`)
- Підтримка 200 мов і автодетекція мови джерела (`source_language` тепер опційний)
- Web UI для тестування сервісу та Swagger-документація
- Переклад HTML-сторінок зі збереженням розмітки

---

### Added
- `GET /languages` endpoint для отримання підтримуваних `source/target` мов і `default_target_language`.
- Rate limit для `POST /translate` з env-керуванням:
  - `NLLB_RATE_LIMIT_ENABLED`
  - `NLLB_RATE_LIMIT_REQUESTS`
  - `NLLB_RATE_LIMIT_WINDOW_SECONDS`
- Структуровані логи для запитів перекладу:
  - `request_id`, `src_lang`, `tgt_lang`, `segments`, `model`, `device`, `latency_ms`, `status`
  - для помилок також `error_class`, `reason`
- Bearer token авторизація через `Authorization: Bearer <token>`.
- Нові/оновлені тести для auth, API-контракту, rate limit, конфігурації й валідації.

### Changed
- `source_language` у `POST /translate` став обов'язковим полем.
- Розширено `SUPPORTED_SOURCE_LANGUAGES` (включно з мовами країн, що межують з Україною).
- Оновлено `docs/openapi.json`, `docs/translator_api.http`, `README.md`, `docs/integration.md`.
- Оновлено `.env.example` (додані параметри auth/rate limit, прибрані небезпечні приклади значень).

### Fixed
- Стабілізовано API-тести (усунено зависання тестового прогону через перехід на unit/integration-light підхід).

### Migration Notes
- Breaking change: клієнти повинні явно передавати `source_language` у кожному запиті `/translate`.
- Для обробки навантаження клієнтам рекомендовано додати обробку `429 Too Many Requests` з retry/backoff.

## Історія Комітів (коротко)

- `f991b2a` Migrate to CTranslate2 + NLLB-200 1.3B INT8
- `09e3693` Додати підтримку перекладу HTML-сторінок
- `9cc42e2` Додати UI для перевірки сервісу та Swagger-документацію
- `8ddf901` Додати підтримку 200 мов та автодетекцію мови джерела
- `8b1dc09` Додати `/languages`, rate limit, структуровані логи та стабільні API-тести
- `9833908` Контракт translate: обов’язковий `source_language`, Bearer auth, оновлена документація та тести
- `f4820d8` Розширити контракт перекладу: `source_language`, мови сусідів України, документація і тести
- `b74cdf9` Додати тести для `NLLB_MAX_LENGTH`: безлімітний режим і валідація
- `d3e09ba` Модель: локальний кеш через `STORAGE_PATH` і офлайн-режим завантаження
- `34dd2eb` Інфраструктура docker compose: `STORAGE_PATH`, `shared_net` і персистентний кеш моделі
- `972278e` API: додати опційний `X-API-Key` для `/translate` і синхронізувати документацію RU/UK
- `25b6786` Стартовий каркас NLLB API: AR->RU/UK, Docker, OpenAPI та інтеграційна документація
