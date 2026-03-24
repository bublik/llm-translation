from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_TARGET_LANGUAGES = {
    "ru": "rus_Cyrl",
    "uk": "ukr_Cyrl",
}


class Settings(BaseSettings):
    """Конфігурація сервісу перекладу, що читається з env."""

    model_config = SettingsConfigDict(env_prefix="NLLB_", env_file=".env", extra="ignore")

    model_name: str = "facebook/nllb-200-distilled-600M"
    src_lang: str = "arb_Arab"
    tgt_lang: str = "rus_Cyrl"
    default_target_language: str = "ru"
    max_length: int = 256

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


settings = Settings()
