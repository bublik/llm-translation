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


# ── Stub: HuggingFace tokenizer ──────────────────────────────────────────────

class DummyTokenizer:
    """Тестовий токенайзер, що імітує AutoTokenizer для NLLB."""

    def __init__(self) -> None:
        self.src_lang: str | None = None

    def __call__(self, text: str) -> dict[str, list[int]]:
        return {"input_ids": [1, 2, 3, 4]}

    def convert_ids_to_tokens(self, ids: list[int]) -> list[str]:
        return [f"tok_{i}" for i in ids]

    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
        return [42] * len(tokens)

    def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
        return "translated"


class StubAutoTokenizer:
    @classmethod
    def from_pretrained(cls, *args: object, **kwargs: object) -> DummyTokenizer:
        return DummyTokenizer()


# ── Stub: CTranslate2 Translator ─────────────────────────────────────────────

class _Hypothesis:
    def __init__(self, tokens: list[str]) -> None:
        self.hypotheses = [tokens]


class DummyCT2Translator:
    """Тестовий замінник ctranslate2.Translator."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.last_call: dict[str, object] = {}

    def translate_batch(
        self,
        source: list[list[str]],
        target_prefix: list[list[str]],
        max_decoding_length: int = 1024,
    ) -> list[_Hypothesis]:
        self.last_call = {
            "source": source,
            "target_prefix": target_prefix,
            "max_decoding_length": max_decoding_length,
        }
        # Повертаємо: мовний префікс + один предбачений токен
        prefix_token = target_prefix[0][0] if target_prefix and target_prefix[0] else "rus_Cyrl"
        return [_Hypothesis([prefix_token, "tok_result"])]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ct2_stub(dummy_translator: DummyCT2Translator) -> types.ModuleType:
    """Будує фейковий модуль ctranslate2 з підкладеним Translator."""
    ct2_stub = types.ModuleType("ctranslate2")
    ct2_stub.Translator = lambda *a, **kw: dummy_translator
    return ct2_stub


def _load_translator_module(monkeypatch: MonkeyPatch, dummy: DummyCT2Translator | None = None):
    """Імпортує app.translator із заміненими ctranslate2 та transformers."""
    if dummy is None:
        dummy = DummyCT2Translator()

    ct2_stub = _make_ct2_stub(dummy)
    transformers_stub = types.ModuleType("transformers")
    transformers_stub.AutoTokenizer = StubAutoTokenizer

    monkeypatch.setitem(sys.modules, "ctranslate2", ct2_stub)
    monkeypatch.setitem(sys.modules, "transformers", transformers_stub)

    # Видаляємо кешований модуль, щоб reload підхопив нові стаби
    sys.modules.pop("app.translator", None)
    translator_module = importlib.import_module("app.translator")
    return importlib.reload(translator_module), dummy


def _build_translator(monkeypatch: MonkeyPatch, max_length: int = 1024):
    """Будує NLLBTranslator із замоканими залежностями."""
    import pathlib

    dummy_ct2 = DummyCT2Translator()
    translator_module, _ = _load_translator_module(monkeypatch, dummy_ct2)

    translator = translator_module.NLLBTranslator.__new__(translator_module.NLLBTranslator)
    translator._ct2 = dummy_ct2
    translator._tokenizer = DummyTokenizer()

    test_settings = Settings(max_length=max_length)
    monkeypatch.setattr(translator_module, "settings", test_settings)

    # Обходимо перевірку існування директорії CT2 моделі
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: True)

    return translator, dummy_ct2


# ── Тести: translate ──────────────────────────────────────────────────────────

def test_translate_returns_string(monkeypatch: MonkeyPatch) -> None:
    """translate() повертає рядок."""
    translator, _ = _build_translator(monkeypatch)
    result = translator.translate("مرحبا", target_language="rus_Cyrl", source_language="arb_Arab")
    assert isinstance(result, str)
    assert result == "translated"


def test_translate_sets_src_lang(monkeypatch: MonkeyPatch) -> None:
    """translate() встановлює src_lang токенайзера до токенізації."""
    translator, _ = _build_translator(monkeypatch)
    translator.translate("Hello", target_language="ukr_Cyrl", source_language="eng_Latn")
    assert translator._tokenizer.src_lang == "eng_Latn"


def test_translate_passes_target_prefix(monkeypatch: MonkeyPatch) -> None:
    """translate_batch отримує target_prefix із кодом цільової мови як токеном."""
    translator, dummy = _build_translator(monkeypatch)
    translator.translate("مرحبا", target_language="rus_Cyrl", source_language="arb_Arab")

    prefix = dummy.last_call["target_prefix"]
    assert len(prefix) == 1
    assert prefix[0][0] == "rus_Cyrl"


def test_translate_uses_max_length_when_positive(monkeypatch: MonkeyPatch) -> None:
    """При max_length > 0 значення передається в translate_batch."""
    translator, dummy = _build_translator(monkeypatch, max_length=512)
    translator.translate("test", target_language="rus_Cyrl", source_language="eng_Latn")
    assert dummy.last_call["max_decoding_length"] == 512


def test_translate_uses_default_max_length_when_zero(monkeypatch: MonkeyPatch) -> None:
    """При max_length=0 використовується _DEFAULT_MAX_DECODING_LENGTH."""
    import app.translator as t_mod
    translator, dummy = _build_translator(monkeypatch, max_length=0)
    translator.translate("test", target_language="rus_Cyrl", source_language="eng_Latn")
    assert dummy.last_call["max_decoding_length"] == t_mod._DEFAULT_MAX_DECODING_LENGTH


def test_translate_skips_language_prefix_token(monkeypatch: MonkeyPatch) -> None:
    """Перший токен з hypotheses (мовний префікс) не входить у декодований результат."""
    translator, dummy = _build_translator(monkeypatch)
    result = translator.translate("hi", target_language="ukr_Cyrl", source_language="eng_Latn")
    assert result == "translated"


def test_translate_chunks_long_text(monkeypatch: MonkeyPatch) -> None:
    """Довгий текст (>_MAX_SOURCE_TOKENS) розбивається на речення і перекладається частинами."""
    import app.translator as t_mod

    dummy_ct2 = DummyCT2Translator()
    translator_module, _ = _load_translator_module(monkeypatch, dummy_ct2)

    # Токенайзер що повертає 257 токенів — перевищує _MAX_SOURCE_TOKENS=256
    class LongTokenizer(DummyTokenizer):
        def __call__(self, text: str) -> dict[str, list[int]]:
            return {"input_ids": list(range(257))}

    import pathlib
    translator = translator_module.NLLBTranslator.__new__(translator_module.NLLBTranslator)
    translator._ct2 = dummy_ct2
    translator._tokenizer = LongTokenizer()
    monkeypatch.setattr(translator_module, "settings", Settings())
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: True)

    # Текст з двома реченнями — має розбитися і перекластися окремо
    call_count = 0
    original_run = translator_module.NLLBTranslator._run

    def counting_run(self, encoded, target_language):
        nonlocal call_count
        call_count += 1
        return original_run(self, encoded, target_language)

    monkeypatch.setattr(translator_module.NLLBTranslator, "_run", counting_run)
    translator.translate("Sentence one. Sentence two.", target_language="ukr_Cyrl", source_language="eng_Latn")
    assert call_count == 2  # 2 речення = 2 виклики _run


def test_split_sentences() -> None:
    """_split_sentences правильно розбиває текст на речення."""
    import app.translator as t_mod

    assert t_mod._split_sentences("Hello. World.") == ["Hello.", "World."]
    assert t_mod._split_sentences("مرحبا؟ كيف حالك؟") == ["مرحبا؟", "كيف حالك؟"]
    assert t_mod._split_sentences("One! Two? Three.") == ["One!", "Two?", "Three."]
    assert t_mod._split_sentences("Single sentence") == ["Single sentence"]


# ── Тести: радіо-глосарій (EuroLLM) ──────────────────────────────────────────

def test_radio_glossary_normalizes() -> None:
    """Пошук у глосарії нечутливий до регістру й крайової пунктуації."""
    import app.translator as t_mod

    assert t_mod._radio_glossary_lookup("Over.", "Ukrainian") == "Прийом."
    assert t_mod._radio_glossary_lookup("over", "Ukrainian") == "Прийом."
    assert t_mod._radio_glossary_lookup("OVER!", "Ukrainian") == "Прийом."
    assert t_mod._radio_glossary_lookup("  Roger that  ", "Ukrainian") == "Прийняв."
    assert t_mod._radio_glossary_lookup("Out.", "Ukrainian") == "Кінець зв'язку."


def test_radio_glossary_none_for_plain_text() -> None:
    """Звичайний текст (не процедурне слово) не збігається з глосарієм."""
    import app.translator as t_mod

    assert t_mod._radio_glossary_lookup("Двигун 3, доповідь.", "Ukrainian") is None
    assert t_mod._radio_glossary_lookup("Roger, рухаюсь на північ.", "Ukrainian") is None


def test_radio_glossary_only_ukrainian_target() -> None:
    """Глосарій активний лише для української цілі."""
    import app.translator as t_mod

    assert t_mod._radio_glossary_lookup("Over.", "Russian") is None
    assert t_mod._radio_glossary_lookup("Over.", "Ukrainian") == "Прийом."


def test_translate_line_shortcircuits_without_model(monkeypatch: MonkeyPatch) -> None:
    """Процедурний рядок повертається з глосарію без виклику моделі; інший — через _run."""
    import app.translator as t_mod

    translator = t_mod.EuroLLMTranslator.__new__(t_mod.EuroLLMTranslator)

    def boom(self, text: str, src: str, tgt: str) -> str:
        raise AssertionError("_run не має викликатись для процедурного рядка")

    monkeypatch.setattr(t_mod.EuroLLMTranslator, "_run", boom)
    assert translator._translate_line("Over.", "Russian", "Ukrainian") == "Прийом."

    # Звичайний рядок має піти в модель (_run).
    calls: list[str] = []

    def record(self, text: str, src: str, tgt: str) -> str:
        calls.append(text)
        return "переклад"

    monkeypatch.setattr(t_mod.EuroLLMTranslator, "_run", record)
    assert translator._translate_line("Двигун 3.", "Russian", "Ukrainian") == "переклад"
    assert calls == ["Двигун 3."]


# ── Тести: Settings ───────────────────────────────────────────────────────────

def test_settings_accept_zero_max_length() -> None:
    """NLLB_MAX_LENGTH=0 проходить валідацію."""
    s = Settings(max_length=0)
    assert s.max_length == 0


def test_settings_reject_negative_max_length() -> None:
    """Від'ємне NLLB_MAX_LENGTH відхиляється."""
    with pytest.raises(ValueError, match="NLLB_MAX_LENGTH must be greater than or equal to 0."):
        Settings(max_length=-1)


def test_settings_reject_invalid_request_text_max_length() -> None:
    """NLLB_REQUEST_TEXT_MAX_LENGTH < 1 відхиляється."""
    with pytest.raises(ValueError, match="NLLB_REQUEST_TEXT_MAX_LENGTH must be greater than or equal to 1."):
        Settings(request_text_max_length=0)


def test_settings_require_bearer_token_when_enabled() -> None:
    """NLLB_BEARER_TOKEN обов'язковий при enabled-прапорці."""
    with pytest.raises(ValueError, match="NLLB_BEARER_TOKEN must be set when NLLB_BEARER_TOKEN_ENABLED=true."):
        Settings(bearer_token_enabled=True, bearer_token=None)


def test_settings_accept_bearer_token_when_enabled() -> None:
    """Bearer-токен приймається при enabled-прапорці."""
    cfg = Settings(bearer_token_enabled=True, bearer_token="token-123")
    assert cfg.bearer_token == "token-123"


def test_settings_reject_invalid_rate_limit_requests() -> None:
    """NLLB_RATE_LIMIT_REQUESTS < 1 відхиляється."""
    with pytest.raises(ValueError, match="NLLB_RATE_LIMIT_REQUESTS must be greater than or equal to 1."):
        Settings(rate_limit_requests=0)


def test_settings_reject_invalid_rate_limit_window_seconds() -> None:
    """NLLB_RATE_LIMIT_WINDOW_SECONDS < 1 відхиляється."""
    with pytest.raises(ValueError, match="NLLB_RATE_LIMIT_WINDOW_SECONDS must be greater than or equal to 1."):
        Settings(rate_limit_window_seconds=0)


def test_settings_default_log_level_is_info() -> None:
    """Дефолтний рівень логування — INFO (щоб latency_ms виводився)."""
    assert Settings().log_level == "INFO"


def test_settings_log_level_normalizes_case() -> None:
    """NLLB_LOG_LEVEL нечутливий до регістру."""
    assert Settings(log_level="debug").log_level == "DEBUG"


def test_settings_reject_invalid_log_level() -> None:
    """Невалідний NLLB_LOG_LEVEL відхиляється."""
    with pytest.raises(ValueError, match="NLLB_LOG_LEVEL must be one of"):
        Settings(log_level="verbose")


def test_settings_default_ct2_device_is_cpu() -> None:
    """CT2 device за замовчуванням — cpu."""
    s = Settings()
    assert s.ct2_device == "cpu"


def test_settings_reject_invalid_ct2_device() -> None:
    """Невалідний NLLB_CT2_DEVICE відхиляється."""
    with pytest.raises(ValueError, match="NLLB_CT2_DEVICE must be 'cpu' or 'cuda'."):
        Settings(ct2_device="gpu")


def test_settings_reject_invalid_ct2_inter_threads() -> None:
    """NLLB_CT2_INTER_THREADS < 1 відхиляється."""
    with pytest.raises(ValueError, match="NLLB_CT2_INTER_THREADS must be greater than or equal to 1."):
        Settings(ct2_inter_threads=0)


def test_settings_model_name_default_is_3_3b() -> None:
    """Code-default для model_name вказує на не-дистильовану модель 3.3B."""
    default = Settings.model_fields["model_name"].default
    assert "3.3B" in default
    assert "distilled" not in default


def test_settings_translation_backend_default_is_nllb() -> None:
    """Code-default для translation_backend — nllb."""
    default = Settings.model_fields["translation_backend"].default
    assert default == "nllb"


def test_settings_translation_backend_accepts_eurollm() -> None:
    """translation_backend приймає значення eurollm."""
    s = Settings(translation_backend="eurollm")
    assert s.translation_backend == "eurollm"


def test_settings_translation_backend_rejects_unknown() -> None:
    """translation_backend відхиляє невідомі значення."""
    with pytest.raises(ValueError, match="NLLB_TRANSLATION_BACKEND must be 'nllb' or 'eurollm'."):
        Settings(translation_backend="openai")


def test_create_translator_returns_nllb(monkeypatch: MonkeyPatch) -> None:
    """create_translator повертає NLLBTranslator при backend=nllb."""
    import pathlib
    translator_module, _ = _load_translator_module(monkeypatch)
    test_settings = Settings(translation_backend="nllb")
    monkeypatch.setattr(translator_module, "settings", test_settings)
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: True)

    translator = translator_module.create_translator()
    assert isinstance(translator, translator_module.NLLBTranslator)


# ── Тести: TranslateRequest / resolve_source_language ────────────────────────

def test_translate_request_enforces_text_length_limit() -> None:
    """Схема застосовує ліміт NLLB_REQUEST_TEXT_MAX_LENGTH."""
    valid_text = "a" * settings.request_text_max_length
    payload = TranslateRequest(text=valid_text, source_language="ar")
    assert payload.text == valid_text

    with pytest.raises(ValidationError):
        TranslateRequest(text="a" * (settings.request_text_max_length + 1), source_language="ar")


def test_translate_request_source_language_defaults_to_none() -> None:
    """source_language за замовчуванням None (автодетекція)."""
    payload = TranslateRequest(text="مرحبا")
    assert payload.source_language is None


def test_supported_source_languages_include_ukraine_neighboring_countries() -> None:
    """Source-мови містять alias для країн-сусідів України."""
    expected_aliases = {"pl", "sk", "hu", "ro", "md", "be", "ru"}
    assert expected_aliases.issubset(SUPPORTED_SOURCE_LANGUAGES.keys())


def test_resolve_source_language_alias() -> None:
    """Перетворення source alias у NLLB-код."""
    assert resolve_source_language("pl") == "pol_Latn"
    assert resolve_source_language("en") == "eng_Latn"
    assert resolve_source_language("ar") == "arb_Arab"


def test_resolve_source_language_nllb_code_case_sensitive() -> None:
    """NLLB-коди зберігають регістр (ukr_Cyrl не перетворюється на ukr_cyrl)."""
    assert resolve_source_language("ukr_Cyrl") == "ukr_Cyrl"
    assert resolve_source_language("rus_Cyrl") == "rus_Cyrl"
    assert resolve_source_language("pol_Latn") == "pol_Latn"


def test_resolve_source_language_uppercase_alias() -> None:
    """Короткі alias-и нечутливі до регістру (AR == ar)."""
    assert resolve_source_language("AR") == "arb_Arab"
    assert resolve_source_language("EN") == "eng_Latn"
