import app.main as main_module
from starlette.requests import Request

from app.main import health, languages, rate_limit_buckets, require_rate_limit, settings, translate
from app.schemas import TranslateRequest


class DummyTranslator:
    """Тестовий перекладач, що повертає маркер цільової мови."""

    def __init__(self) -> None:
        """Ініціалізує слоти для останніх параметрів перекладу."""
        self.last_source_language: str | None = None
        self.last_target_language: str | None = None

    def translate(self, text: str, target_language: str, source_language: str) -> str:
        """Емулює переклад для тестів API-шару."""
        self.last_source_language = source_language
        self.last_target_language = target_language
        return f"{target_language}:{text}"


def _build_request(client_ip: str = "127.0.0.1") -> Request:
    """Створює мінімальний request-об'єкт для unit-тестів."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/translate",
        "headers": [],
        "client": (client_ip, 12345),
    }
    return Request(scope)


def test_health() -> None:
    """Перевіряє, що health повертає статус ok."""
    assert health() == {"status": "ok"}


def test_languages() -> None:
    """Перевіряє, що `/languages` повертає source/target мапи."""
    payload = languages()
    assert payload.source_languages["pl"] == "pol_Latn"
    assert payload.source_languages["en"] == "eng_Latn"
    assert payload.target_languages["uk"] == "ukr_Cyrl"


def test_translate_uses_default_ru_target_language() -> None:
    """Перевіряє дефолтну цільову мову ru, якщо параметр не передано."""
    translator = DummyTranslator()
    payload = TranslateRequest(text="مرحبا", source_language="ar")

    response = translate(request=_build_request(), payload=payload, _=None, __=None, translator=translator)

    assert response.translation == "rus_Cyrl:مرحبا"
    assert response.source_language == "arb_Arab"
    assert response.target_language == "rus_Cyrl"
    assert translator.last_source_language == "arb_Arab"


def test_translate_resolves_source_language_alias() -> None:
    """Перевіряє резолв source_language alias у NLLB-код."""
    translator = DummyTranslator()
    payload = TranslateRequest(text="Cześć", source_language="pl", target_language="uk")

    response = translate(request=_build_request(), payload=payload, _=None, __=None, translator=translator)

    assert response.source_language == "pol_Latn"
    assert response.target_language == "ukr_Cyrl"
    assert translator.last_source_language == "pol_Latn"


def test_translate_auto_detects_source_language(monkeypatch) -> None:
    """Перевіряє автодетекцію вхідної мови, якщо source_language не передано."""
    monkeypatch.setattr(main_module, "_detect_language", lambda text: "pol_Latn")
    translator = DummyTranslator()
    payload = TranslateRequest(text="Cześć", target_language="uk")

    response = translate(request=_build_request(), payload=payload, _=None, __=None, translator=translator)

    assert response.source_language == "pol_Latn"
    assert response.target_language == "ukr_Cyrl"
    assert translator.last_source_language == "pol_Latn"


def test_translate_auto_keyword_triggers_detection(monkeypatch) -> None:
    """Перевіряє, що source_language='auto' активує автодетекцію."""
    monkeypatch.setattr(main_module, "_detect_language", lambda text: "deu_Latn")
    translator = DummyTranslator()
    payload = TranslateRequest(text="Hallo", source_language="auto")

    response = translate(request=_build_request(), payload=payload, _=None, __=None, translator=translator)

    assert response.source_language == "deu_Latn"


def test_translate_raises_422_when_language_not_detected(monkeypatch) -> None:
    """Перевіряє `422`, якщо автодетекція не змогла визначити мову."""
    from fastapi import HTTPException

    def _fail(_text: str) -> str:
        raise HTTPException(status_code=422, detail="Could not detect source language.")

    monkeypatch.setattr(main_module, "_detect_language", _fail)
    translator = DummyTranslator()
    payload = TranslateRequest(text="???")

    try:
        translate(request=_build_request(), payload=payload, _=None, __=None, translator=translator)
        assert False, "Очікувався HTTPException(422)"
    except HTTPException as exc:
        assert exc.status_code == 422


def test_rate_limit_exceeded(monkeypatch) -> None:
    """Перевіряє `429`, коли ліміт запитів у вікні перевищено."""
    from fastapi import HTTPException

    rate_limit_buckets.clear()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)

    request = _build_request(client_ip="10.0.0.1")
    require_rate_limit(request)

    try:
        require_rate_limit(request)
        assert False, "Очікувався HTTPException(429), але помилка не виникла."
    except HTTPException as exc:
        assert exc.status_code == 429
