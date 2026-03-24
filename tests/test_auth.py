from app.main import is_authorized_request, settings


def test_authorization_disabled_allows_request(monkeypatch) -> None:
    """Перевіряє, що без увімкненого auth запит дозволяється."""
    monkeypatch.setattr(settings, "api_key_enabled", False)
    monkeypatch.setattr(settings, "bearer_token_enabled", False)

    assert is_authorized_request(api_key=None, bearer_token=None) is True


def test_authorization_with_api_key(monkeypatch) -> None:
    """Перевіряє доступ за `X-API-Key`, якщо увімкнено API key auth."""
    monkeypatch.setattr(settings, "api_key_enabled", True)
    monkeypatch.setattr(settings, "api_key", "key-123")
    monkeypatch.setattr(settings, "bearer_token_enabled", False)

    assert is_authorized_request(api_key="key-123", bearer_token=None) is True
    assert is_authorized_request(api_key="wrong", bearer_token=None) is False


def test_authorization_with_bearer_token(monkeypatch) -> None:
    """Перевіряє доступ за bearer-токеном, якщо він увімкнений."""
    monkeypatch.setattr(settings, "api_key_enabled", False)
    monkeypatch.setattr(settings, "bearer_token_enabled", True)
    monkeypatch.setattr(settings, "bearer_token", "token-123")

    assert is_authorized_request(api_key=None, bearer_token="token-123") is True
    assert is_authorized_request(api_key=None, bearer_token="wrong") is False


def test_authorization_allows_any_enabled_method(monkeypatch) -> None:
    """Перевіряє, що при двох режимах достатньо одного валідного методу."""
    monkeypatch.setattr(settings, "api_key_enabled", True)
    monkeypatch.setattr(settings, "api_key", "key-123")
    monkeypatch.setattr(settings, "bearer_token_enabled", True)
    monkeypatch.setattr(settings, "bearer_token", "token-123")

    assert is_authorized_request(api_key="key-123", bearer_token=None) is True
    assert is_authorized_request(api_key=None, bearer_token="token-123") is True
    assert is_authorized_request(api_key="bad", bearer_token="bad") is False
