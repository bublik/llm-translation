import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from lingua import Language, LanguageDetectorBuilder

from app.config import (
    LANGUAGE_DETECTION_FAILED_DETAIL,
    LANGUAGES_DESCRIPTION,
    LANGUAGES_ENDPOINT_PATH,
    LANGUAGES_SUMMARY,
    API_CONTACT_NAME,
    API_DESCRIPTION,
    API_KEY_HEADER_NAME,
    API_TAGS,
    API_TITLE,
    API_VERSION,
    HEALTH_ENDPOINT_PATH,
    HEALTH_OK_STATUS,
    HTTP_STATUS_MODEL_UNAVAILABLE,
    HTTP_STATUS_TOO_MANY_REQUESTS,
    HTTP_STATUS_UNAUTHORIZED,
    HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE,
    INVALID_OR_MISSING_API_KEY_DETAIL,
    INVALID_OR_MISSING_BEARER_TOKEN_DETAIL,
    RATE_LIMIT_EXCEEDED_DETAIL,
    RATE_LIMIT_RESPONSE_DESCRIPTION,
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

_DETECTION_LANGUAGE_MAP: dict[Language, str] = {
    Language.AFRIKAANS: "afr_Latn",
    Language.ARABIC: "arb_Arab",
    Language.ARMENIAN: "hye_Armn",
    Language.AZERBAIJANI: "azj_Latn",
    Language.BASQUE: "eus_Latn",
    Language.BELARUSIAN: "bel_Cyrl",
    Language.BENGALI: "ben_Beng",
    Language.BOKMAL: "nob_Latn",
    Language.BOSNIAN: "bos_Latn",
    Language.BULGARIAN: "bul_Cyrl",
    Language.CATALAN: "cat_Latn",
    Language.CHINESE: "zho_Hans",
    Language.CROATIAN: "hrv_Latn",
    Language.CZECH: "ces_Latn",
    Language.DANISH: "dan_Latn",
    Language.DUTCH: "nld_Latn",
    Language.ENGLISH: "eng_Latn",
    Language.ESPERANTO: "epo_Latn",
    Language.ESTONIAN: "est_Latn",
    Language.FINNISH: "fin_Latn",
    Language.FRENCH: "fra_Latn",
    Language.GANDA: "lug_Latn",
    Language.GEORGIAN: "kat_Geor",
    Language.GERMAN: "deu_Latn",
    Language.GREEK: "ell_Grek",
    Language.GUJARATI: "guj_Gujr",
    Language.HEBREW: "heb_Hebr",
    Language.HINDI: "hin_Deva",
    Language.HUNGARIAN: "hun_Latn",
    Language.ICELANDIC: "isl_Latn",
    Language.INDONESIAN: "ind_Latn",
    Language.IRISH: "gle_Latn",
    Language.ITALIAN: "ita_Latn",
    Language.JAPANESE: "jpn_Jpan",
    Language.KAZAKH: "kaz_Cyrl",
    Language.KOREAN: "kor_Hang",
    Language.LATVIAN: "lvs_Latn",
    Language.LITHUANIAN: "lit_Latn",
    Language.MACEDONIAN: "mkd_Cyrl",
    Language.MALAY: "zsm_Latn",
    Language.MAORI: "mri_Latn",
    Language.MARATHI: "mar_Deva",
    Language.MONGOLIAN: "khk_Cyrl",
    Language.NYNORSK: "nno_Latn",
    Language.PERSIAN: "pes_Arab",
    Language.POLISH: "pol_Latn",
    Language.PORTUGUESE: "por_Latn",
    Language.PUNJABI: "pan_Guru",
    Language.ROMANIAN: "ron_Latn",
    Language.RUSSIAN: "rus_Cyrl",
    Language.SERBIAN: "srp_Cyrl",
    Language.SHONA: "sna_Latn",
    Language.SLOVAK: "slk_Latn",
    Language.SLOVENE: "slv_Latn",
    Language.SOMALI: "som_Latn",
    Language.SOTHO: "sot_Latn",
    Language.SPANISH: "spa_Latn",
    Language.SWAHILI: "swh_Latn",
    Language.SWEDISH: "swe_Latn",
    Language.TAGALOG: "tgl_Latn",
    Language.TAMIL: "tam_Taml",
    Language.TELUGU: "tel_Telu",
    Language.THAI: "tha_Thai",
    Language.TSONGA: "tso_Latn",
    Language.TSWANA: "tsn_Latn",
    Language.TURKISH: "tur_Latn",
    Language.UKRAINIAN: "ukr_Cyrl",
    Language.URDU: "urd_Arab",
    Language.VIETNAMESE: "vie_Latn",
    Language.WELSH: "cym_Latn",
    Language.XHOSA: "xho_Latn",
    Language.YORUBA: "yor_Latn",
    Language.ZULU: "zul_Latn",
}
_language_detector = None

from app.schemas import ErrorResponse, LanguagesResponse, TranslateRequest, TranslateResponse

if TYPE_CHECKING:
    from app.translator import NLLBTranslator

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    contact={"name": API_CONTACT_NAME},
    openapi_tags=list(API_TAGS),
)
logger = logging.getLogger("app.main")
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
rate_limit_lock = threading.Lock()
rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)


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


def _get_language_detector():
    """Повертає синглтон детектора мови, ініціалізуючи його за першого виклику."""
    global _language_detector
    if _language_detector is None:
        _language_detector = (
            LanguageDetectorBuilder.from_languages(*_DETECTION_LANGUAGE_MAP.keys()).build()
        )
    return _language_detector


def _detect_language(text: str) -> str:
    """Автоматично визначає NLLB-код вхідної мови тексту.

    Args:
        text: Вхідний текст для аналізу.

    Returns:
        Код вхідної мови NLLB.

    Raises:
        HTTPException: Якщо мову не вдалося визначити.
    """
    detected = _get_language_detector().detect_language_of(text)
    nllb_code = _DETECTION_LANGUAGE_MAP.get(detected) if detected is not None else None
    if nllb_code is None:
        raise HTTPException(
            status_code=HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE,
            detail=LANGUAGE_DETECTION_FAILED_DETAIL,
        )
    return nllb_code


def resolve_source_language(source_language: str | None, text: str = "") -> str:
    """Визначає NLLB-код вхідної мови для поточного запиту.

    Args:
        source_language: Alias вхідної мови, NLLB-код, `auto` або `None` для автодетекції.
        text: Вхідний текст — використовується лише при автодетекції.

    Returns:
        Код вхідної мови NLLB.

    Raises:
        HTTPException: Якщо alias не підтримується або мову не вдалося визначити.
    """
    if source_language is None or source_language.strip().lower() == "auto":
        return _detect_language(text)
    alias = source_language.strip().lower()
    resolved_language = SUPPORTED_SOURCE_LANGUAGES.get(alias)
    if resolved_language is None:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_LANGUAGES.keys()))
        raise HTTPException(
            status_code=HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE,
            detail=UNSUPPORTED_SOURCE_LANGUAGE_DETAIL_TEMPLATE.format(alias=alias, supported=supported),
        )
    return resolved_language


def is_authorized_request(api_key: str | None, bearer_token: str | None) -> bool:
    """Перевіряє, чи запит містить валідні авторизаційні дані.

    Args:
        api_key: Значення заголовка `X-API-Key`.
        bearer_token: Значення bearer-токена без префікса `Bearer`.

    Returns:
        `True`, якщо запит авторизований згідно поточних налаштувань.
    """
    api_key_required = settings.api_key_enabled
    bearer_required = settings.bearer_token_enabled
    if not api_key_required and not bearer_required:
        return True

    valid_api_key = api_key_required and bool(api_key and api_key == settings.api_key)
    valid_bearer = bearer_required and bool(bearer_token and bearer_token == settings.bearer_token)
    return valid_api_key or valid_bearer


def require_auth(
    api_key: str | None = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> None:
    """Перевіряє API-ключ або bearer-токен для захищених ендпоінтів.

    Args:
        api_key: Значення заголовка `X-API-Key` з HTTP-запиту.
        bearer: Облікові дані з заголовка `Authorization: Bearer ...`.

    Raises:
        HTTPException: Якщо облікові дані відсутні або невалідні.
    """
    bearer_token = None
    if bearer and bearer.scheme.lower() == "bearer":
        bearer_token = bearer.credentials

    if is_authorized_request(api_key=api_key, bearer_token=bearer_token):
        return

    detail = INVALID_OR_MISSING_API_KEY_DETAIL
    if settings.bearer_token_enabled and not settings.api_key_enabled:
        detail = INVALID_OR_MISSING_BEARER_TOKEN_DETAIL
    raise HTTPException(status_code=HTTP_STATUS_UNAUTHORIZED, detail=detail)


def extract_client_key(request: Request) -> str:
    """Повертає ключ клієнта для rate limit."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def require_rate_limit(request: Request) -> None:
    """Перевіряє ліміт частоти запитів для ендпоінта перекладу."""
    if not settings.rate_limit_enabled:
        return

    now = time.monotonic()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests
    key = extract_client_key(request)

    with rate_limit_lock:
        bucket = rate_limit_buckets[key]
        while bucket and now - bucket[0] >= window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=HTTP_STATUS_TOO_MANY_REQUESTS, detail=RATE_LIMIT_EXCEEDED_DETAIL)
        bucket.append(now)


def get_model_device(translator: Any) -> str:
    """Повертає device моделі перекладу, якщо доступно."""
    model = getattr(translator, "_model", None)
    device = getattr(model, "device", None)
    if device is None:
        return "unknown"
    return str(device)


@app.get(
    HEALTH_ENDPOINT_PATH,
    tags=["system"],
    summary="Перевірка доступності сервісу",
    description="Повертає базовий статус живості застосунку.",
)
def health() -> dict[str, str]:
    """Ендпоінт liveness-перевірки."""
    return {"status": HEALTH_OK_STATUS}


@app.get(
    LANGUAGES_ENDPOINT_PATH,
    tags=["system"],
    summary=LANGUAGES_SUMMARY,
    description=LANGUAGES_DESCRIPTION,
    response_model=LanguagesResponse,
)
def languages() -> LanguagesResponse:
    """Повертає підтримувані alias-и source/target мов."""
    return LanguagesResponse(
        source_languages=SUPPORTED_SOURCE_LANGUAGES,
        target_languages=SUPPORTED_TARGET_LANGUAGES,
        default_target_language=settings.default_target_language,
    )


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
        HTTP_STATUS_TOO_MANY_REQUESTS: {
            "model": ErrorResponse,
            "description": RATE_LIMIT_RESPONSE_DESCRIPTION,
        },
        HTTP_STATUS_MODEL_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": MODEL_UNAVAILABLE_RESPONSE_DESCRIPTION,
        }
    },
)
def translate(
    request: Request,
    payload: TranslateRequest,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
    translator: Any = Depends(get_translator),
) -> TranslateResponse:
    """Приймає текст і повертає переклад із метаданими моделі.

    Args:
        payload: Вхідний payload із текстом та опційною цільовою мовою.
        translator: Ініціалізований екземпляр перекладача.

    Returns:
        Об'єкт із перекладом і метаданими застосованої конфігурації.
    """
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started_at = time.perf_counter()
    resolved_source_language = resolve_source_language(payload.source_language, payload.text)
    resolved_target_language = resolve_target_language(payload.target_language)
    device = get_model_device(translator)
    segments = 1
    try:
        translated = translator.translate(
            payload.text,
            target_language=resolved_target_language,
            source_language=resolved_source_language,
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "translate_request",
                    "request_id": request_id,
                    "src_lang": resolved_source_language,
                    "tgt_lang": resolved_target_language,
                    "segments": segments,
                    "model": settings.model_name,
                    "device": device,
                    "latency_ms": latency_ms,
                    "status": "success",
                },
                ensure_ascii=False,
            )
        )
        return TranslateResponse(
            translation=translated,
            source_language=resolved_source_language,
            target_language=resolved_target_language,
            model_name=settings.model_name,
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.error(
            json.dumps(
                {
                    "event": "translate_request",
                    "request_id": request_id,
                    "src_lang": resolved_source_language,
                    "tgt_lang": resolved_target_language,
                    "segments": segments,
                    "model": settings.model_name,
                    "device": device,
                    "latency_ms": latency_ms,
                    "status": "error",
                    "error_class": exc.__class__.__name__,
                    "reason": str(exc),
                },
                ensure_ascii=False,
            )
        )
        raise
