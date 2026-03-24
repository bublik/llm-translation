from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_TITLE = "NLLB-200 Translation Service"
API_VERSION = "0.3.0"
API_DESCRIPTION = (
    "HTTP API для перекладу тексту у підтримувані цільові мови за допомогою NLLB-200. "
    "Арабська (`arb_Arab`) використовується як типовий приклад вхідного тексту."
)
API_CONTACT_NAME = "Speech Translate Service"
API_TAGS = (
    {"name": "system", "description": "Службові ендпоінти сервісу."},
    {"name": "translation", "description": "Ендпоінти перекладу тексту."},
)
API_KEY_HEADER_NAME = "X-API-Key"
HEALTH_ENDPOINT_PATH = "/health"
TRANSLATE_ENDPOINT_PATH = "/translate"
HEALTH_OK_STATUS = "ok"
INVALID_OR_MISSING_API_KEY_DETAIL = "Invalid or missing API key."
INVALID_OR_MISSING_BEARER_TOKEN_DETAIL = "Invalid or missing bearer token."
MODEL_UNAVAILABLE_DETAIL_PREFIX = "Model is unavailable"
UNSUPPORTED_TARGET_LANGUAGE_DETAIL_TEMPLATE = "Unsupported target_language '{alias}'. Supported: {supported}"
UNSUPPORTED_SOURCE_LANGUAGE_DETAIL_TEMPLATE = "Unsupported source_language '{alias}'. Supported: {supported}"
HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE = 422
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_MODEL_UNAVAILABLE = 503
UNAUTHORIZED_RESPONSE_DESCRIPTION = "Невалідні або відсутні облікові дані авторизації."
MODEL_UNAVAILABLE_RESPONSE_DESCRIPTION = "Модель недоступна або не ініціалізувалась."
TRANSLATE_SUMMARY = "Переклад тексту у підтримувану мову"
TRANSLATE_DESCRIPTION = (
    "Виконує переклад одного тексту (наприклад, арабського `arb_Arab`) "
    "у підтримувану цільову мову."
)
TEXT_MIN_LENGTH = 1

SUPPORTED_TARGET_LANGUAGES = {
    "ru": "rus_Cyrl",
    "uk": "ukr_Cyrl",
}
SUPPORTED_SOURCE_LANGUAGES = {
    "ar": "arb_Arab",
    "pl": "pol_Latn",  # Poland
    "sk": "slk_Latn",  # Slovakia
    "hu": "hun_Latn",  # Hungary
    "ro": "ron_Latn",  # Romania
    "md": "ron_Latn",  # Moldova (Romanian)
    "be": "bel_Cyrl",  # Belarus
    "ru": "rus_Cyrl",  # Russia
}


class Settings(BaseSettings):
    """Конфігурація сервісу перекладу, що читається з env."""

    model_config = SettingsConfigDict(env_prefix="NLLB_", env_file=".env", extra="ignore")

    model_name: str = "facebook/nllb-200-distilled-600M"
    tgt_lang: str = "rus_Cyrl"
    default_target_language: str = "ru"
    api_key_enabled: bool = False
    api_key: str | None = None
    bearer_token_enabled: bool = False
    bearer_token: str | None = None
    model_cache_dir: str = "/app/storage/huggingface"
    transformers_offline: bool = False
    max_length: int = 1024
    request_text_max_length: int = 10_000

    @field_validator("default_target_language")
    @classmethod
    def validate_default_target_language(cls, value: str) -> str:
        """Перевіряє, що дефолтний alias цільової мови підтримується.

        Args:
            value: Alias цільової мови (`ru` або `uk`).

        Returns:
            Нормалізований alias цільової мови.

        Raises:
            ValueError: Якщо alias не входить до підтримуваного набору.
        """
        normalized_value = value.strip().lower()
        if normalized_value not in SUPPORTED_TARGET_LANGUAGES:
            supported = ", ".join(sorted(SUPPORTED_TARGET_LANGUAGES.keys()))
            raise ValueError(f"Unsupported NLLB_DEFAULT_TARGET_LANGUAGE '{value}'. Supported: {supported}")
        return normalized_value

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str | None) -> str | None:
        """Перевіряє формат API ключа доступу.

        Args:
            value: Значення API-ключа з env.

        Returns:
            Обрізане значення ключа або None.
        """
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @field_validator("bearer_token")
    @classmethod
    def validate_bearer_token(cls, value: str | None) -> str | None:
        """Перевіряє формат bearer токена доступу.

        Args:
            value: Значення bearer-токена з env.

        Returns:
            Обрізане значення токена або None.
        """
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @model_validator(mode="after")
    def validate_auth_settings(self) -> "Settings":
        """Перевіряє узгодженість auth-настройок."""
        if self.api_key_enabled and not self.api_key:
            raise ValueError("NLLB_API_KEY must be set when NLLB_API_KEY_ENABLED=true.")
        if self.bearer_token_enabled and not self.bearer_token:
            raise ValueError("NLLB_BEARER_TOKEN must be set when NLLB_BEARER_TOKEN_ENABLED=true.")
        return self

    @field_validator("max_length")
    @classmethod
    def validate_max_length(cls, value: int) -> int:
        """Перевіряє обмеження довжини генерації перекладу.

        Args:
            value: Значення `NLLB_MAX_LENGTH` з env.

        Returns:
            Ціле невід'ємне значення довжини.

        Raises:
            ValueError: Якщо значення від'ємне.
        """
        if value < 0:
            raise ValueError("NLLB_MAX_LENGTH must be greater than or equal to 0.")
        return value

    @field_validator("model_cache_dir")
    @classmethod
    def validate_model_cache_dir(cls, value: str) -> str:
        """Перевіряє директорію локального кешу моделі.

        Args:
            value: Шлях до директорії кешу з env.

        Returns:
            Нормалізований непорожній шлях.

        Raises:
            ValueError: Якщо шлях порожній.
        """
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("NLLB_MODEL_CACHE_DIR must not be empty.")
        return normalized_value

    @field_validator("request_text_max_length")
    @classmethod
    def validate_request_text_max_length(cls, value: int) -> int:
        """Перевіряє ліміт довжини вхідного тексту для API.

        Args:
            value: Значення `NLLB_REQUEST_TEXT_MAX_LENGTH` з env.

        Returns:
            Додатне ціле значення.

        Raises:
            ValueError: Якщо значення менше 1.
        """
        if value < TEXT_MIN_LENGTH:
            raise ValueError("NLLB_REQUEST_TEXT_MAX_LENGTH must be greater than or equal to 1.")
        return value


settings = Settings()
