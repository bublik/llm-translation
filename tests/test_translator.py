from __future__ import annotations

import importlib
import sys
import types

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.config import SUPPORTED_SOURCE_LANGUAGES, Settings, settings
from app.main import resolve_source_language
from app.schemas import TranslateRequest


class DummyTokenizer:
    """Тестовий токенайзер для перевірки параметрів виклику генерації."""

    def __init__(self) -> None:
        """Ініціалізує тестовий стан токенайзера."""
        self.src_lang: str | None = None

    def __call__(self, text: str, return_tensors: str) -> dict[str, list[int]]:
        """Повертає фіктивні вхідні токени для моделі.

        Args:
            text: Вхідний текст.
            return_tensors: Формат тензорів (не використовується у тесті).

        Returns:
            Мінімальний словник вхідних токенів.
        """
        return {"input_ids": [1, 2, 3]}

    def convert_tokens_to_ids(self, target_language: str) -> int:
        """Повертає фіктивний id цільової мови.

        Args:
            target_language: Код цільової мови.

        Returns:
            Сталий id токена початку генерації.
        """
        return 777

    def batch_decode(self, translated_tokens: list[list[int]], skip_special_tokens: bool) -> list[str]:
        """Імітує декодування токенів перекладу.

        Args:
            translated_tokens: Токени, що повернула модель.
            skip_special_tokens: Прапорець пропуску спецтокенів.

        Returns:
            Список із одним декодованим рядком.
        """
        return ["translated"]


class DummyModel:
    """Тестова модель, що зберігає kwargs останнього виклику generate."""

    def __init__(self) -> None:
        """Ініціалізує контейнер для kwargs."""
        self.last_generate_kwargs: dict[str, object] = {}

    def generate(self, **kwargs: object) -> list[list[int]]:
        """Зберігає kwargs генерації та повертає фіктивні токени.

        Args:
            **kwargs: Аргументи виклику генерації.

        Returns:
            Фіктивні токени перекладу.
        """
        self.last_generate_kwargs = kwargs
        return [[101, 102]]


def _load_translator_module(monkeypatch: MonkeyPatch):
    """Імпортує `app.translator` з підкладеним фейковим `transformers`.

    Args:
        monkeypatch: Фікстура pytest для тимчасової підміни модулів.

    Returns:
        Імпортований модуль `app.translator`.
    """

    class StubAutoTokenizer:
        """Заглушка токенайзера для імпорту модуля."""

        @classmethod
        def from_pretrained(cls, model_name: str) -> DummyTokenizer:
            """Повертає тестовий токенайзер замість реального.

            Args:
                model_name: Назва моделі (у тесті не використовується).

            Returns:
                Екземпляр `DummyTokenizer`.
            """
            return DummyTokenizer()

    class StubAutoModel:
        """Заглушка моделі для імпорту модуля."""

        @classmethod
        def from_pretrained(cls, model_name: str) -> DummyModel:
            """Повертає тестову модель замість реальної.

            Args:
                model_name: Назва моделі (у тесті не використовується).

            Returns:
                Екземпляр `DummyModel`.
            """
            return DummyModel()

    transformers_stub = types.ModuleType("transformers")
    transformers_stub.AutoTokenizer = StubAutoTokenizer
    transformers_stub.AutoModelForSeq2SeqLM = StubAutoModel
    monkeypatch.setitem(sys.modules, "transformers", transformers_stub)
    translator_module = importlib.import_module("app.translator")
    return importlib.reload(translator_module)


def _build_translator_with_max_length(monkeypatch: MonkeyPatch, max_length: int) -> tuple[object, DummyModel]:
    """Створює перекладач із заміненими залежностями для unit-тесту.

    Args:
        monkeypatch: Фікстура pytest для підміни модулів.
        max_length: Значення ліміту довжини генерації.

    Returns:
        Кортеж із підготовленого перекладача та тестової моделі.
    """
    translator_module = _load_translator_module(monkeypatch)
    translator = translator_module.NLLBTranslator.__new__(translator_module.NLLBTranslator)
    translator._tokenizer = DummyTokenizer()
    model = DummyModel()
    translator._model = model
    test_settings = Settings(max_length=max_length)
    monkeypatch.setattr(translator_module, "settings", test_settings)
    return translator, model


def test_translate_does_not_pass_max_length_when_zero(monkeypatch: MonkeyPatch) -> None:
    """Перевіряє, що при max_length=0 аргумент у generate не передається."""
    translator, model = _build_translator_with_max_length(monkeypatch=monkeypatch, max_length=0)

    result = translator.translate("مرحبا", target_language="rus_Cyrl", source_language="arb_Arab")

    assert result == "translated"
    assert model.last_generate_kwargs["forced_bos_token_id"] == 777
    assert "max_length" not in model.last_generate_kwargs


def test_translate_passes_max_length_when_positive(monkeypatch: MonkeyPatch) -> None:
    """Перевіряє, що при max_length>0 аргумент передається в generate."""
    translator, model = _build_translator_with_max_length(monkeypatch=monkeypatch, max_length=1024)

    result = translator.translate("مرحبا", target_language="ukr_Cyrl", source_language="arb_Arab")

    assert result == "translated"
    assert model.last_generate_kwargs["forced_bos_token_id"] == 777
    assert model.last_generate_kwargs["max_length"] == 1024


def test_settings_accept_zero_max_length() -> None:
    """Перевіряє, що `NLLB_MAX_LENGTH=0` проходить валідацію налаштувань."""
    settings = Settings(max_length=0)
    assert settings.max_length == 0


def test_settings_reject_negative_max_length() -> None:
    """Перевіряє, що від'ємне `NLLB_MAX_LENGTH` відхиляється валідацією."""
    with pytest.raises(ValueError, match="NLLB_MAX_LENGTH must be greater than or equal to 0."):
        Settings(max_length=-1)


def test_settings_reject_invalid_request_text_max_length() -> None:
    """Перевіряє, що `NLLB_REQUEST_TEXT_MAX_LENGTH < 1` відхиляється."""
    with pytest.raises(ValueError, match="NLLB_REQUEST_TEXT_MAX_LENGTH must be greater than or equal to 1."):
        Settings(request_text_max_length=0)


def test_settings_require_bearer_token_when_enabled() -> None:
    """Перевіряє, що `NLLB_BEARER_TOKEN` обов'язковий при enabled-прапорці."""
    with pytest.raises(ValueError, match="NLLB_BEARER_TOKEN must be set when NLLB_BEARER_TOKEN_ENABLED=true."):
        Settings(bearer_token_enabled=True, bearer_token=None)


def test_settings_accept_bearer_token_when_enabled() -> None:
    """Перевіряє, що bearer-токен приймається при enabled-прапорці."""
    cfg = Settings(bearer_token_enabled=True, bearer_token="token-123")
    assert cfg.bearer_token == "token-123"


def test_settings_reject_invalid_rate_limit_requests() -> None:
    """Перевіряє, що `NLLB_RATE_LIMIT_REQUESTS < 1` відхиляється."""
    with pytest.raises(ValueError, match="NLLB_RATE_LIMIT_REQUESTS must be greater than or equal to 1."):
        Settings(rate_limit_requests=0)


def test_settings_reject_invalid_rate_limit_window_seconds() -> None:
    """Перевіряє, що `NLLB_RATE_LIMIT_WINDOW_SECONDS < 1` відхиляється."""
    with pytest.raises(ValueError, match="NLLB_RATE_LIMIT_WINDOW_SECONDS must be greater than or equal to 1."):
        Settings(rate_limit_window_seconds=0)


def test_translate_request_enforces_text_length_limit() -> None:
    """Перевіряє, що схема застосовує ліміт `NLLB_REQUEST_TEXT_MAX_LENGTH`."""
    valid_text = "a" * settings.request_text_max_length
    payload = TranslateRequest(text=valid_text, source_language="ar")
    assert payload.text == valid_text

    with pytest.raises(ValidationError):
        TranslateRequest(text="a" * (settings.request_text_max_length + 1), source_language="ar")


def test_translate_request_source_language_defaults_to_none() -> None:
    """Перевіряє, що `source_language` за замовчуванням None (автодетекція)."""
    payload = TranslateRequest(text="مرحبا")
    assert payload.source_language is None


def test_supported_source_languages_include_ukraine_neighboring_countries() -> None:
    """Перевіряє, що source-мови містять alias для країн-сусідів України."""
    expected_aliases = {"pl", "sk", "hu", "ro", "md", "be", "ru"}
    assert expected_aliases.issubset(SUPPORTED_SOURCE_LANGUAGES.keys())


def test_resolve_source_language_alias() -> None:
    """Перевіряє перетворення source alias у NLLB-код."""
    assert resolve_source_language("pl") == "pol_Latn"
    assert resolve_source_language("en") == "eng_Latn"
    assert resolve_source_language("ar") == "arb_Arab"
