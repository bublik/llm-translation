from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import (
    API_CONTACT_NAME,
    API_DESCRIPTION,
    API_KEY_HEADER_NAME,
    API_TAGS,
    API_TITLE,
    API_VERSION,
    HEALTH_ENDPOINT_PATH,
    HEALTH_OK_STATUS,
    HTTP_STATUS_MODEL_UNAVAILABLE,
    HTTP_STATUS_UNAUTHORIZED,
    HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE,
    INVALID_OR_MISSING_API_KEY_DETAIL,
    MODEL_UNAVAILABLE_DETAIL_PREFIX,
    MODEL_UNAVAILABLE_RESPONSE_DESCRIPTION,
    SUPPORTED_SOURCE_LANGUAGES,
    SUPPORTED_TARGET_LANGUAGES,
    TRANSLATE_DESCRIPTION,
    TRANSLATE_ENDPOINT_PATH,
    TRANSLATE_SUMMARY,
    UNAUTHORIZED_RESPONSE_DESCRIPTION,
    UNSUPPORTED_SOURCE_LANGUAGE_DETAIL_TEMPLATE,
    UNSUPPORTED_TARGET_LANGUAGE_DETAIL_TEMPLATE,
    settings,
)
from app.schemas import ErrorResponse, TranslateRequest, TranslateResponse

if TYPE_CHECKING:
    from app.translator import NLLBTranslator

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    contact={"name": API_CONTACT_NAME},
    openapi_tags=list(API_TAGS),
)
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def get_translator() -> Any:
    """Повертає синглтон перекладача, ініціалізуючи модель за першого запиту."""
    translator = getattr(app.state, "translator", None)
    if translator is None:
        try:
            from app.translator import NLLBTranslator

            translator = NLLBTranslator()
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=HTTP_STATUS_MODEL_UNAVAILABLE,
                detail=f"{MODEL_UNAVAILABLE_DETAIL_PREFIX}: {exc}",
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
        raise HTTPException(
            status_code=HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE,
            detail=UNSUPPORTED_TARGET_LANGUAGE_DETAIL_TEMPLATE.format(alias=alias, supported=supported),
        )
    return resolved_language


def resolve_source_language(source_language: str | None) -> str:
    """Визначає NLLB-код вхідної мови для поточного запиту.

    Args:
        source_language: Alias вхідної мови з запиту.

    Returns:
        Код вхідної мови NLLB.

    Raises:
        HTTPException: Якщо alias не підтримується.
    """
    if source_language is None:
        return settings.src_lang

    alias = source_language.strip().lower()
    resolved_language = SUPPORTED_SOURCE_LANGUAGES.get(alias)
    if resolved_language is None:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_LANGUAGES.keys()))
        raise HTTPException(
            status_code=HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE,
            detail=UNSUPPORTED_SOURCE_LANGUAGE_DETAIL_TEMPLATE.format(alias=alias, supported=supported),
        )
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
            status_code=HTTP_STATUS_UNAUTHORIZED,
            detail=INVALID_OR_MISSING_API_KEY_DETAIL,
        )


@app.get(
    HEALTH_ENDPOINT_PATH,
    tags=["system"],
    summary="Перевірка доступності сервісу",
    description="Повертає базовий статус живості застосунку.",
)
def health() -> dict[str, str]:
    """Ендпоінт liveness-перевірки."""
    return {"status": HEALTH_OK_STATUS}


@app.post(
    TRANSLATE_ENDPOINT_PATH,
    tags=["translation"],
    summary=TRANSLATE_SUMMARY,
    description=TRANSLATE_DESCRIPTION,
    response_model=TranslateResponse,
    responses={
        HTTP_STATUS_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": UNAUTHORIZED_RESPONSE_DESCRIPTION,
        },
        HTTP_STATUS_MODEL_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": MODEL_UNAVAILABLE_RESPONSE_DESCRIPTION,
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
    resolved_source_language = resolve_source_language(payload.source_language)
    resolved_target_language = resolve_target_language(payload.target_language)
    translated = translator.translate(
        payload.text,
        target_language=resolved_target_language,
        source_language=resolved_source_language,
    )
    return TranslateResponse(
        translation=translated,
        source_language=resolved_source_language,
        target_language=resolved_target_language,
        model_name=settings.model_name,
    )
