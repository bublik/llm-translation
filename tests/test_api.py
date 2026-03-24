from fastapi.testclient import TestClient

from app.main import app


class DummyTranslator:
    """Тестовий перекладач, що повертає маркер цільової мови."""

    def __init__(self) -> None:
        """Ініціалізує слоти для останніх параметрів перекладу."""
        self.last_source_language: str | None = None
        self.last_target_language: str | None = None

    def translate(self, text: str, target_language: str, source_language: str) -> str:
        """Емулює переклад для інтеграційних API-тестів.

        Args:
            text: Вхідний текст.
            target_language: Цільова NLLB-мова.
            source_language: Вхідна NLLB-мова.

        Returns:
            Текст із префіксом цільової мови.
        """
        self.last_source_language = source_language
        self.last_target_language = target_language
        return f"{target_language}:{text}"


def test_health() -> None:
    """Перевіряє, що ендпоінт health повертає статус ok."""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_translate_uses_default_ru_target_language() -> None:
    """Перевіряє дефолтну цільову мову ru, якщо параметр не передано."""
    app.state.translator = DummyTranslator()
    client = TestClient(app)

    response = client.post("/translate", json={"text": "مرحبا", "source_language": "ar"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["translation"] == "rus_Cyrl:مرحبا"
    assert payload["source_language"] == "arb_Arab"
    assert payload["target_language"] == "rus_Cyrl"


def test_translate_to_ukrainian() -> None:
    """Перевіряє переклад у українську через target_language=uk."""
    app.state.translator = DummyTranslator()
    client = TestClient(app)

    response = client.post("/translate", json={"text": "مرحبا", "source_language": "ar", "target_language": "uk"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["translation"] == "ukr_Cyrl:مرحبا"
    assert payload["source_language"] == "arb_Arab"
    assert payload["target_language"] == "ukr_Cyrl"


def test_translate_to_russian_explicitly() -> None:
    """Перевіряє явний вибір російської через target_language=ru."""
    app.state.translator = DummyTranslator()
    client = TestClient(app)

    response = client.post("/translate", json={"text": "مرحبا", "source_language": "ar", "target_language": "ru"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["translation"] == "rus_Cyrl:مرحبا"
    assert payload["target_language"] == "rus_Cyrl"


def test_translate_rejects_unsupported_target_language() -> None:
    """Перевіряє валідацію target_language для непідтриманого значення."""
    app.state.translator = DummyTranslator()
    client = TestClient(app)

    response = client.post("/translate", json={"text": "مرحبا", "source_language": "ar", "target_language": "de"})
    payload = response.json()

    assert response.status_code == 422
    assert payload["detail"][0]["loc"] == ["body", "target_language"]


def test_translate_rejects_missing_source_language() -> None:
    """Перевіряє, що `source_language` є обов'язковим полем запиту."""
    app.state.translator = DummyTranslator()
    client = TestClient(app)

    response = client.post("/translate", json={"text": "مرحبا", "target_language": "ru"})
    payload = response.json()

    assert response.status_code == 422
    assert payload["detail"][0]["loc"] == ["body", "source_language"]


def test_translate_resolves_source_language_alias() -> None:
    """Перевіряє резолв source_language alias у NLLB-код."""
    translator = DummyTranslator()
    app.state.translator = translator
    client = TestClient(app)

    response = client.post("/translate", json={"text": "Cześć", "source_language": "pl", "target_language": "uk"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["source_language"] == "pol_Latn"
    assert payload["target_language"] == "ukr_Cyrl"
    assert translator.last_source_language == "pol_Latn"
