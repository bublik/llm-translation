from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import SUPPORTED_TARGET_LANGUAGES, settings
from app.schemas import ErrorResponse, TranslateRequest, TranslateResponse

if TYPE_CHECKING:
    from app.translator import NLLBTranslator

app = FastAPI(
    title="NLLB-200 AR->(RU|UK) Service",
    version="0.3.0",
    description=(
        "HTTP API для перекладу тексту з арабської (arb_Arab) "
        "на російську (rus_Cyrl) або українську (ukr_Cyrl) за допомогою NLLB-200."
    ),
    contact={"name": "Speech Translate Service"},
    openapi_tags=[
        {"name": "system", "description": "Службові ендпоінти сервісу."},
        {"name": "translation", "description": "Ендпоінти перекладу тексту."},
    ],
)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_translator() -> Any:
    """Повертає синглтон перекладача, ініціалізуючи модель за першого запиту."""
    translator = getattr(app.state, "translator", None)
    if translator is None:
        try:
            from app.translator import NLLBTranslator

            translator = NLLBTranslator()
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=503,
                detail=f"Model is unavailable: {exc}",
            ) from exc
        app.state.translator = translator
    return translator


def resolve_target_language(target_language: str | None) -> str:
    """Визначає NLLB-код цільової мови для поточного запиту.

    Args:
        target_language: Alias цільової мови з запиту (`ru` або `uk`).

    Returns:
        Код мови NLLB, який використовується в інференсі.

    Raises:
        HTTPException: Якщо alias не підтримується.
    """
    alias = (target_language or settings.default_target_language).strip().lower()
    resolved_language = SUPPORTED_TARGET_LANGUAGES.get(alias)
    if resolved_language is None:
        supported = ", ".join(sorted(SUPPORTED_TARGET_LANGUAGES.keys()))
        raise HTTPException(status_code=422, detail=f"Unsupported target_language '{alias}'. Supported: {supported}")
    return resolved_language


def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    """Перевіряє API-ключ для захищених ендпоінтів.

    Args:
        api_key: Значення заголовка `X-API-Key` з HTTP-запиту.

    Raises:
        HTTPException: Якщо ключ відсутній або невалідний.
    """
    if not settings.api_key_enabled:
        return
    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


@app.get(
    "/health",
    tags=["system"],
    summary="Перевірка доступності сервісу",
    description="Повертає базовий статус живості застосунку.",
)
def health() -> dict[str, str]:
    """Ендпоінт liveness-перевірки."""
    return {"status": "ok"}


@app.post(
    "/translate",
    tags=["translation"],
    summary="Переклад з AR у RU або UK",
    description="Виконує переклад одного тексту з `arb_Arab` у `rus_Cyrl` або `ukr_Cyrl`.",
    response_model=TranslateResponse,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Невалідний або відсутній API ключ.",
        },
        503: {
            "model": ErrorResponse,
            "description": "Модель недоступна або не ініціалізувалась.",
        }
    },
)
def translate(
    payload: TranslateRequest,
    _: None = Depends(require_api_key),
    translator: Any = Depends(get_translator),
) -> TranslateResponse:
    """Приймає текст і повертає переклад із метаданими моделі.

    Args:
        payload: Вхідний payload із текстом та опційною цільовою мовою.
        translator: Ініціалізований екземпляр перекладача.

    Returns:
        Об'єкт із перекладом і метаданими застосованої конфігурації.
    """
    resolved_target_language = resolve_target_language(payload.target_language)
    translated = translator.translate(payload.text, target_language=resolved_target_language)
    return TranslateResponse(
        translation=translated,
        source_language=settings.src_lang,
        target_language=resolved_target_language,
        model_name=settings.model_name,
    )
