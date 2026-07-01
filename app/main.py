import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.responses import HTMLResponse
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
    ROOT_DESCRIPTION,
    ROOT_ENDPOINT_PATH,
    ROOT_SUMMARY,
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
    from app.translator import EuroLLMTranslator, NLLBTranslator

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    contact={"name": API_CONTACT_NAME},
    openapi_tags=list(API_TAGS),
)
# Без явної конфігурації логер `app.main` пропагує до root (за замовчуванням
# WARNING, без хендлера), тож INFO-логи (зокрема latency_ms кожного запиту) не
# виводяться — видно лише access-логи uvicorn. Налаштовуємо root-хендлер тут.
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app.main")
logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
rate_limit_lock = threading.Lock()
rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)


def get_translator() -> Any:
    """Повертає синглтон перекладача, ініціалізуючи модель за першого запиту."""
    translator = getattr(app.state, "translator", None)
    if translator is None:
        try:
            from app.translator import create_translator

            translator = create_translator()
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
    stripped = source_language.strip()
    # Спочатку точне співпадіння (для NLLB-кодів типу ukr_Cyrl),
    # потім lowercase (для коротких alias-ів типу AR → ar).
    resolved_language = SUPPORTED_SOURCE_LANGUAGES.get(stripped) or SUPPORTED_SOURCE_LANGUAGES.get(stripped.lower())
    alias = stripped
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
    """Повертає device транслятора."""
    ct2 = getattr(translator, "_ct2", None)
    device = getattr(ct2, "device", None)
    if device is not None:
        return str(device)
    if hasattr(translator, "_llm"):
        return "cpu"
    return "unknown"


# ── HTML-переклад ────────────────────────────────────────────────────────────

class _HTMLTextTranslator(HTMLParser):
    """Обходить HTML і перекладає лише текстові вузли.

    Теги, атрибути, коментарі та вміст <script>/<style>/<code>/<pre>
    передаються до виводу без змін.
    """

    # Вміст цих тегів перекладати не потрібно
    _NO_TRANSLATE: frozenset[str] = frozenset(
        {"script", "style", "noscript", "code", "pre", "math", "svg"}
    )

    def __init__(self, translate_fn: Callable[[str], str]) -> None:
        super().__init__(convert_charrefs=False)
        self._fn = translate_fn
        self._out: list[str] = []
        self._skip_depth: int = 0

    # ── helpers ──────────────────────────────────────────────────────────────

    def _serialize_attrs(self, attrs: list[tuple[str, str | None]]) -> str:
        parts: list[str] = []
        for name, value in attrs:
            if value is None:
                parts.append(f" {name}")
            else:
                parts.append(f' {name}="{value.replace(chr(34), "&quot;")}"')
        return "".join(parts)

    # ── HTMLParser callbacks ──────────────────────────────────────────────────

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._NO_TRANSLATE:
            self._skip_depth += 1
        self._out.append(f"<{tag}{self._serialize_attrs(attrs)}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._NO_TRANSLATE and self._skip_depth:
            self._skip_depth -= 1
        self._out.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Самозакриваючі теги (<br/>, <img/> тощо)."""
        self._out.append(f"<{tag}{self._serialize_attrs(attrs)}/>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data.strip():
            self._out.append(data)
            return
        stripped = data.strip()
        leading  = data[: len(data) - len(data.lstrip())]
        trailing = data[len(data.rstrip()) :]
        try:
            self._out.append(leading + self._fn(stripped) + trailing)
        except Exception:
            self._out.append(data)

    def handle_comment(self, data: str) -> None:
        self._out.append(f"<!--{data}-->")

    def handle_entityref(self, name: str) -> None:
        self._out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._out.append(f"&#{name};")

    def handle_decl(self, decl: str) -> None:
        self._out.append(f"<!{decl}>")

    def result(self) -> str:
        return "".join(self._out)


def _translate_html(html_text: str, translate_fn: Callable[[str], str]) -> str:
    """Перекладає текстові вузли HTML, зберігаючи теги та атрибути незмінними."""
    parser = _HTMLTextTranslator(translate_fn)
    parser.feed(html_text)
    return parser.result()


def _html_to_plain(html_text: str) -> str:
    """Вилучає видимий текст із HTML (для автодетекції мови)."""
    return re.sub(r"<[^>]+>", " ", html_text).strip()


# ── HTML сторінка ─────────────────────────────────────────────────────────────

_ROOT_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NLLB-200 Перекладач</title>
  <style>
    :root {
      --blue: #1a73e8;
      --blue-hover: #1558b0;
      --blue-light: #e8f0fe;
      --border: #dadce0;
      --bg: #f8f9fa;
      --text: #202124;
      --text-muted: #5f6368;
      --radius: 8px;
      --shadow: 0 1px 3px rgba(0,0,0,.12), 0 1px 2px rgba(0,0,0,.08);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Google Sans', Roboto, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }

    /* ── Header ───────────────────────────────────── */
    header {
      background: #fff;
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      height: 60px;
      display: flex;
      align-items: center;
      gap: 14px;
      position: sticky;
      top: 0;
      z-index: 10;
    }

    .logo { font-size: 20px; font-weight: 600; color: var(--blue); }

    .version {
      font-size: 11px;
      color: var(--text-muted);
      background: var(--bg);
      padding: 2px 8px;
      border-radius: 10px;
      border: 1px solid var(--border);
    }

    .header-right { margin-left: auto; display: flex; align-items: center; gap: 8px; }

    .auth-toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      border: 1px solid var(--border);
      border-radius: 20px;
      background: transparent;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      cursor: pointer;
      transition: all .15s;
    }

    .auth-toggle:hover { border-color: var(--blue); color: var(--blue); }
    .auth-toggle.open  { border-color: var(--blue); color: var(--blue); background: var(--blue-light); }
    .auth-toggle.saved { border-color: #34a853; color: #137333; }
    .auth-toggle.saved:hover { background: #e6f4ea; }

    .auth-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #34a853;
      display: none;
    }

    .auth-toggle.saved .auth-dot { display: inline-block; }

    /* ── Auth bar ─────────────────────────────────── */
    .auth-bar {
      background: #fffde7;
      border-bottom: 1px solid #ffe082;
      padding: 0;
      max-height: 0;
      overflow: hidden;
      transition: max-height .25s ease, padding .25s ease;
    }

    .auth-bar.open {
      max-height: 120px;
      padding: 14px 24px;
    }

    .auth-bar-inner {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .auth-bar label {
      font-size: 13px;
      font-weight: 500;
      color: #5f4b00;
      white-space: nowrap;
    }

    .auth-input {
      flex: 1;
      min-width: 180px;
      max-width: 340px;
      padding: 8px 12px;
      border: 1px solid #ffe082;
      border-radius: 6px;
      font-size: 13px;
      font-family: 'Roboto Mono', 'Courier New', monospace;
      outline: none;
      background: #fff;
      color: var(--text);
    }

    .auth-input:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(26,115,232,.15); }

    .auth-save {
      padding: 8px 16px;
      background: var(--blue);
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: background .15s;
      white-space: nowrap;
    }

    .auth-save:hover { background: var(--blue-hover); }

    .auth-forget {
      padding: 8px 12px;
      background: transparent;
      color: var(--text-muted);
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 13px;
      cursor: pointer;
      transition: all .15s;
      white-space: nowrap;
    }

    .auth-forget:hover { color: #d93025; border-color: #d93025; }

    .auth-hint {
      font-size: 12px;
      color: #8d6e00;
    }

    /* ── Layout ───────────────────────────────────── */
    main {
      max-width: 1200px;
      margin: 0 auto;
      padding: 28px 16px 48px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }

    /* ── Translator card ──────────────────────────── */
    .translator {
      background: #fff;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      border: 1px solid var(--border);
      overflow: hidden;
    }

    /* ── Language bar ─────────────────────────────── */
    .lang-bar-row {
      display: grid;
      grid-template-columns: 1fr 52px 1fr;
      border-bottom: 1px solid var(--border);
      background: #fff;
    }

    .lang-bar {
      display: flex;
      align-items: center;
      padding: 8px 16px;
      gap: 10px;
      min-height: 52px;
    }

    .lang-bar.source { border-right: 1px solid var(--border); }
    .lang-bar.target { border-left: 1px solid var(--border); }

    .lang-bar select {
      border: none;
      background: transparent;
      font-size: 14px;
      font-weight: 500;
      color: var(--text);
      cursor: pointer;
      outline: none;
      padding: 6px 4px;
      border-radius: 4px;
      max-width: 100%;
    }

    .lang-bar select:hover { background: var(--bg); }

    .detected {
      font-size: 12px;
      color: var(--text-muted);
      white-space: nowrap;
    }

    .swap-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      cursor: pointer;
      color: var(--text-muted);
      font-size: 20px;
      transition: color .15s, transform .2s;
      width: 100%;
      height: 100%;
      border-radius: 0;
    }

    .swap-btn:hover { color: var(--blue); transform: rotate(180deg); }

    /* ── Panels ───────────────────────────────────── */
    .panels {
      display: grid;
      grid-template-columns: 1fr 1fr;
      min-height: 240px;
    }

    .panel {
      display: flex;
      flex-direction: column;
    }

    .panel.source { border-right: 1px solid var(--border); }

    textarea {
      flex: 1;
      padding: 20px;
      font-size: 18px;
      line-height: 1.65;
      border: none;
      outline: none;
      resize: none;
      font-family: inherit;
      color: var(--text);
      background: #fff;
    }

    textarea::placeholder { color: #bdc1c6; }

    .translation {
      flex: 1;
      padding: 20px;
      font-size: 18px;
      line-height: 1.65;
      background: #f8f9fa;
      color: var(--blue);
      white-space: pre-wrap;
      word-wrap: break-word;
      min-height: 180px;
    }

    .translation.loading   { color: var(--text-muted); font-style: italic; font-size: 15px; }
    .translation.error     { color: #d93025; font-size: 14px; line-height: 1.5; }
    .translation.html-out  {
      font-family: 'Roboto Mono', 'Courier New', monospace;
      font-size: 13px;
      color: #37474f;
      white-space: pre-wrap;
      background: #f5f5f5;
    }

    .icon-btn.active { background: var(--blue-light); color: var(--blue); }

    /* ── Panel footers ────────────────────────────── */
    .panel-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px;
      border-top: 1px solid var(--border);
      min-height: 46px;
      background: #fff;
    }

    .panel.target .panel-footer { background: #f8f9fa; }

    .char-count { font-size: 13px; color: var(--text-muted); }
    .char-count.over { color: #d93025; }

    .model-name { font-size: 12px; color: var(--text-muted); }

    .row-btns { display: flex; gap: 2px; }

    .icon-btn {
      background: transparent;
      border: none;
      cursor: pointer;
      color: var(--text-muted);
      padding: 7px 9px;
      border-radius: 50%;
      font-size: 15px;
      line-height: 1;
      transition: background .15s, color .15s;
      user-select: none;
    }

    .icon-btn:hover { background: #ebebeb; color: var(--text); }

    /* ── Docs section ─────────────────────────────── */
    .docs {
      background: #fff;
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      border: 1px solid var(--border);
      padding: 32px;
    }

    .docs h2 {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 20px;
      color: var(--text);
    }

    .doc-links {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 32px;
    }

    .doc-link {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 18px;
      border-radius: 20px;
      text-decoration: none;
      font-size: 14px;
      font-weight: 500;
      border: 1px solid var(--border);
      color: var(--text);
      transition: all .15s;
    }

    .doc-link:hover { background: var(--blue-light); border-color: var(--blue); color: var(--blue); }

    .doc-link.primary {
      background: var(--blue); color: #fff; border-color: var(--blue);
    }

    .doc-link.primary:hover { background: var(--blue-hover); }

    .docs h3 {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 14px;
      color: var(--text);
    }

    .ep-list { display: flex; flex-direction: column; gap: 10px; }

    .ep-card {
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 14px 18px;
      display: grid;
      grid-template-columns: 56px 1fr auto;
      gap: 14px;
      align-items: center;
    }

    .method {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .4px;
      padding: 4px 8px;
      border-radius: 4px;
      text-align: center;
    }

    .GET  { background: #e6f4ea; color: #137333; }
    .POST { background: #fce8e6; color: #c5221f; }

    .ep-body .path {
      font-family: 'Roboto Mono', 'Courier New', monospace;
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 3px;
    }

    .ep-body .desc { font-size: 13px; color: var(--text-muted); }

    .auth-chip {
      font-size: 11px;
      padding: 3px 9px;
      border-radius: 10px;
      background: #fef7e0;
      color: #b06000;
      border: 1px solid #fdd663;
      white-space: nowrap;
    }

    /* ── Responsive ───────────────────────────────── */
    @media (max-width: 720px) {
      .panels { grid-template-columns: 1fr; }
      .panel.source { border-right: none; border-bottom: 1px solid var(--border); }
      .lang-bar-row { grid-template-columns: 1fr 44px 1fr; }
      .docs { padding: 20px; }
      .ep-card { grid-template-columns: 48px 1fr; }
      .auth-chip { display: none; }
    }
  </style>
</head>
<body>

<header>
  <span class="logo">NLLB-200 Перекладач</span>
  <span class="version" id="ver">v…</span>
  <div class="header-right">
    <button class="auth-toggle" id="auth-toggle" title="Налаштування авторизації">
      🔑 API ключ
      <span class="auth-dot"></span>
    </button>
  </div>
</header>

<div class="auth-bar" id="auth-bar">
  <div class="auth-bar-inner">
    <label for="auth-input">Токен / API ключ:</label>
    <input type="password" class="auth-input" id="auth-input"
           placeholder="Введіть ваш API ключ або Bearer-токен…" autocomplete="off">
    <button class="auth-save" id="auth-save">Зберегти</button>
    <button class="auth-forget" id="auth-forget">Видалити</button>
    <span class="auth-hint">Зберігається в localStorage браузера.</span>
  </div>
</div>

<main>

  <!-- ── Translator ── -->
  <div class="translator">

    <div class="lang-bar-row">
      <div class="lang-bar source">
        <select id="src-lang">
          <option value="auto">Визначити автоматично</option>
        </select>
        <span class="detected" id="detected"></span>
      </div>

      <button class="swap-btn" id="swap-btn" title="Поміняти мови місцями">⇄</button>

      <div class="lang-bar target">
        <select id="tgt-lang"></select>
      </div>
    </div>

    <div class="panels">
      <div class="panel source">
        <textarea id="src-text" placeholder="Введіть текст…" maxlength="10000" spellcheck="false" autocomplete="off"></textarea>
        <div class="panel-footer">
          <span class="char-count" id="chars">0 / 10 000</span>
          <div class="row-btns">
            <button class="icon-btn" id="html-btn" title="HTML-режим: перекладати текст, зберігати теги">&lt;/&gt;</button>
            <button class="icon-btn" id="clear-btn" title="Очистити">✕</button>
          </div>
        </div>
      </div>

      <div class="panel target">
        <div class="translation" id="tgt-text"></div>
        <div class="panel-footer">
          <span class="model-name" id="model-name"></span>
          <div class="row-btns">
            <button class="icon-btn" id="copy-btn" title="Копіювати переклад">⎘</button>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- ── Docs ── -->
  <div class="docs">
    <h2>Документація API</h2>

    <div class="doc-links">
      <a class="doc-link primary" href="/docs">⚡ Swagger UI</a>
      <a class="doc-link" href="/redoc">📖 ReDoc</a>
      <a class="doc-link" href="/openapi.json" target="_blank">{ } OpenAPI JSON</a>
      <a class="doc-link" href="/languages" target="_blank">🌐 Список мов</a>
    </div>

    <h3>Доступні ендпоінти</h3>
    <div class="ep-list" id="ep-list"></div>
  </div>

</main>

<script>
(function () {
  'use strict';

  const MAX = 10000;
  const DEBOUNCE = 600;

  const srcLangEl  = document.getElementById('src-lang');
  const tgtLangEl  = document.getElementById('tgt-lang');
  const srcTextEl  = document.getElementById('src-text');
  const tgtTextEl  = document.getElementById('tgt-text');
  const charsEl    = document.getElementById('chars');
  const detectedEl = document.getElementById('detected');
  const modelEl    = document.getElementById('model-name');
  const clearBtn   = document.getElementById('clear-btn');
  const copyBtn    = document.getElementById('copy-btn');
  const swapBtn    = document.getElementById('swap-btn');
  const htmlBtn    = document.getElementById('html-btn');

  let htmlMode = false;

  htmlBtn.addEventListener('click', () => {
    htmlMode = !htmlMode;
    htmlBtn.classList.toggle('active', htmlMode);
    srcTextEl.placeholder = htmlMode ? '<p>Вставте HTML з тегами…</p>' : 'Введіть текст…';
    tgtTextEl.classList.toggle('html-out', htmlMode);
    lastText = '';
    if (srcTextEl.value.trim()) scheduleTranslate();
  });
  const verEl      = document.getElementById('ver');
  const epListEl   = document.getElementById('ep-list');
  const authToggle = document.getElementById('auth-toggle');
  const authBar    = document.getElementById('auth-bar');
  const authInput  = document.getElementById('auth-input');
  const authSave   = document.getElementById('auth-save');
  const authForget = document.getElementById('auth-forget');

  // ── Auth state ───────────────────────────────────
  const AUTH_REQUIRED = __AUTH_REQUIRED__;
  const LS_KEY = 'nllb_token';
  let token = localStorage.getItem(LS_KEY) || '';

  function authUISync() {
    authToggle.classList.toggle('saved', !!token);
    if (token) authInput.value = token;
  }

  function openAuthBar() {
    authBar.classList.add('open');
    authToggle.classList.add('open');
    authToggle.classList.remove('saved');
    setTimeout(() => authInput.focus(), 50);
  }

  function closeAuthBar() {
    authBar.classList.remove('open');
    authToggle.classList.remove('open');
    authUISync();
  }

  authToggle.addEventListener('click', () => {
    authBar.classList.contains('open') ? closeAuthBar() : openAuthBar();
  });

  authSave.addEventListener('click', () => {
    token = authInput.value.trim();
    if (token) localStorage.setItem(LS_KEY, token);
    else localStorage.removeItem(LS_KEY);
    closeAuthBar();
    lastText = '';       // примусово перекласти ще раз
    scheduleTranslate();
  });

  authInput.addEventListener('keydown', e => { if (e.key === 'Enter') authSave.click(); });

  authForget.addEventListener('click', () => {
    token = '';
    authInput.value = '';
    localStorage.removeItem(LS_KEY);
    authUISync();
  });

  let timer = null;
  let lastText = '', lastSrc = '', lastTgt = '';

  // ── Відомі назви мов ────────────────────────────
  const NAMES = {
    ar: 'Арабська',   en: 'Англійська', pl: 'Польська',
    sk: 'Словацька',  hu: 'Угорська',   ro: 'Румунська',
    md: 'Молдовська', be: 'Білоруська', ru: 'Російська',
    uk: 'Українська',
  };

  function langLabel(code) {
    return NAMES[code] ? NAMES[code] + ' (' + code + ')' : code;
  }

  // ── Завантаження мов ────────────────────────────
  async function loadLanguages() {
    try {
      const res  = await fetch('/languages');
      const data = await res.json();

      verEl.textContent = 'v' + (data.version || '0.3.0');

      // Джерельні мови: спочатку короткі alias-и, потім NLLB-коди
      const shortAliases = ['ar','en','pl','sk','hu','ro','md','be','ru'];
      const allSrc = Object.keys(data.source_languages);
      const nllbCodes = allSrc.filter(k => !shortAliases.includes(k)).sort();

      const grpCommon = document.createElement('optgroup');
      grpCommon.label = 'Поширені мови';
      shortAliases.filter(a => data.source_languages[a]).forEach(a => {
        const o = new Option(langLabel(a), a);
        grpCommon.appendChild(o);
      });
      srcLangEl.appendChild(grpCommon);

      const grpNllb = document.createElement('optgroup');
      grpNllb.label = 'NLLB-200 коди (' + nllbCodes.length + ')';
      nllbCodes.forEach(code => {
        grpNllb.appendChild(new Option(code, code));
      });
      srcLangEl.appendChild(grpNllb);

      // Цільові мови
      Object.keys(data.target_languages).forEach(alias => {
        tgtLangEl.appendChild(new Option(langLabel(alias), alias));
      });
      if (data.default_target_language) {
        tgtLangEl.value = data.default_target_language;
      }

    } catch (e) {
      console.error('Не вдалося завантажити список мов:', e);
    }
  }

  // ── Переклад ────────────────────────────────────
  async function translate() {
    const text = srcTextEl.value.trim();
    const src  = srcLangEl.value;
    const tgt  = tgtLangEl.value;

    if (!text) {
      resetTarget();
      return;
    }
    if (text === lastText && src === lastSrc && tgt === lastTgt) return;

    setLoading();

    try {
      const body = {
        text,
        target_language: tgt || null,
        source_language: (src === 'auto') ? null : src,
        format: htmlMode ? 'html' : 'text',
      };

      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['X-API-Key'] = token;
        headers['Authorization'] = 'Bearer ' + token;
      }

      const res = await fetch('/translate', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });

      if (res.status === 401) {
        setError('Помилка 401: невалідний або відсутній токен. Введіть ключ у полі вище.');
        openAuthBar();
        return;
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        setError('Помилка ' + res.status + ': ' + (err.detail || res.statusText));
        return;
      }

      const data = await res.json();
      tgtTextEl.textContent = data.translation;
      tgtTextEl.className = 'translation' + (htmlMode ? ' html-out' : '');
      detectedEl.textContent = (src === 'auto') ? '← ' + data.source_language : '';
      modelEl.textContent = data.model_name;

      lastText = text; lastSrc = src; lastTgt = tgt;

    } catch (e) {
      setError("Помилка з'єднання з сервером.");
    }
  }

  function setLoading() {
    tgtTextEl.textContent = 'Перекладаю…';
    tgtTextEl.className = 'translation loading';
    modelEl.textContent = '';
  }

  function setError(msg) {
    tgtTextEl.textContent = msg;
    tgtTextEl.className = 'translation error';
    modelEl.textContent = '';
  }

  function resetTarget() {
    tgtTextEl.textContent = '';
    tgtTextEl.className = 'translation' + (htmlMode ? ' html-out' : '');
    detectedEl.textContent = '';
    modelEl.textContent = '';
    lastText = ''; lastSrc = ''; lastTgt = '';
  }

  function scheduleTranslate() {
    clearTimeout(timer);
    timer = setTimeout(translate, DEBOUNCE);
  }

  // ── Лічильник символів ──────────────────────────
  function updateChars() {
    const n = srcTextEl.value.length;
    charsEl.textContent = n.toLocaleString('uk') + ' / 10\u202F000';
    charsEl.classList.toggle('over', n >= MAX);
  }

  // ── Swap ─────────────────────────────────────────
  swapBtn.addEventListener('click', () => {
    const tgtText = tgtTextEl.textContent;
    const tgtClass = tgtTextEl.className;
    if (!tgtText || tgtClass.includes('loading') || tgtClass.includes('error')) return;

    srcTextEl.value = tgtText;

    // Намагаємося встановити мову джерела = поточна цільова
    const tgtVal = tgtLangEl.value;
    const srcOpts = Array.from(srcLangEl.options).map(o => o.value);
    if (srcOpts.includes(tgtVal)) srcLangEl.value = tgtVal;
    else srcLangEl.value = 'auto';

    updateChars();
    lastText = '';
    scheduleTranslate();
  });

  // ── Очистити ────────────────────────────────────
  clearBtn.addEventListener('click', () => {
    srcTextEl.value = '';
    updateChars();
    resetTarget();
    srcTextEl.focus();
  });

  // ── Копіювати ───────────────────────────────────
  copyBtn.addEventListener('click', async () => {
    const text = tgtTextEl.textContent;
    if (!text || tgtTextEl.className.includes('error')) return;
    try {
      await navigator.clipboard.writeText(text);
      copyBtn.textContent = '✓';
      setTimeout(() => { copyBtn.textContent = '⎘'; }, 1600);
    } catch (_) {}
  });

  srcTextEl.addEventListener('input', () => { updateChars(); scheduleTranslate(); });
  srcLangEl.addEventListener('change', scheduleTranslate);
  tgtLangEl.addEventListener('change', scheduleTranslate);

  // ── Список ендпоінтів ───────────────────────────
  const ENDPOINTS = [
    { method:'GET',  path:'/',           summary:'Інтерфейс перекладача',  desc:'Ця сторінка — інтерактивний UI для перекладу тексту.',                           auth: false },
    { method:'GET',  path:'/health',     summary:'Перевірка доступності',  desc:'Повертає <code>{"status":"ok"}</code> — liveness-check сервісу.',                auth: false },
    { method:'GET',  path:'/languages',  summary:'Підтримувані мови',      desc:'Повертає мап alias → NLLB-код для вхідних і цільових мов.',                      auth: false },
    { method:'POST', path:'/translate',  summary:'Переклад тексту',        desc:'Перекладає текст у вибрану цільову мову (ru/uk). Підтримує автодетекцію мови.',  auth: true  },
    { method:'GET',  path:'/docs',       summary:'Swagger UI',              desc:'Інтерактивна документація OpenAPI у форматі Swagger.',                           auth: false },
    { method:'GET',  path:'/redoc',      summary:'ReDoc',                   desc:'Альтернативна документація OpenAPI.',                                             auth: false },
  ];

  ENDPOINTS.forEach(ep => {
    const card = document.createElement('div');
    card.className = 'ep-card';
    card.innerHTML =
      '<span class="method ' + ep.method + '">' + ep.method + '</span>' +
      '<div class="ep-body">' +
        '<div class="path">' + ep.path + '</div>' +
        '<div class="desc"><strong>' + ep.summary + '</strong> — ' + ep.desc + '</div>' +
      '</div>' +
      (ep.auth ? '<span class="auth-chip">🔒 auth</span>' : '<span></span>');
    epListEl.appendChild(card);
  });

  // ── Старт ────────────────────────────────────────
  authUISync();
  if (AUTH_REQUIRED && !token) openAuthBar();
  loadLanguages();
  srcTextEl.focus();
})();
</script>

</body>
</html>"""


@app.get(
    ROOT_ENDPOINT_PATH,
    tags=["system"],
    summary=ROOT_SUMMARY,
    description=ROOT_DESCRIPTION,
    response_class=HTMLResponse,
    include_in_schema=False,
)
def root() -> HTMLResponse:
    """Повертає інтерактивний веб-інтерфейс перекладача."""
    auth_required = settings.api_key_enabled or settings.bearer_token_enabled
    html = _ROOT_HTML.replace("__AUTH_REQUIRED__", "true" if auth_required else "false")
    return HTMLResponse(content=html)


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
    # Для HTML-режиму визначаємо мову за видимим текстом (без тегів)
    detect_from = _html_to_plain(payload.text) if payload.format == "html" else payload.text
    resolved_source_language = resolve_source_language(payload.source_language, detect_from)
    resolved_target_language = resolve_target_language(payload.target_language)
    device = get_model_device(translator)
    segments = 1
    try:
        if payload.format == "html":
            translated = _translate_html(
                payload.text,
                lambda text: translator.translate(
                    text,
                    target_language=resolved_target_language,
                    source_language=resolved_source_language,
                ),
            )
        else:
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
