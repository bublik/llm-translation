from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_TITLE = "NLLB-200 Translation Service"
API_VERSION = "0.3.0"
API_DESCRIPTION = (
    "HTTP API для перекладу тексту у підтримувані цільові мови за допомогою NLLB-200. "
    "Арабська (`arb_Arab`) використовується як типовий приклад вхідного тексту."
)
API_CONTACT_NAME = "Speech Translate Service"
API_TAGS = (
    {"name": "system", "description": "Службові ендпоінти сервісу."},
    {"name": "translation", "description": "Ендпоінти перекладу тексту."},
)
API_KEY_HEADER_NAME = "X-API-Key"
HEALTH_ENDPOINT_PATH = "/health"
TRANSLATE_ENDPOINT_PATH = "/translate"
LANGUAGES_ENDPOINT_PATH = "/languages"
HEALTH_OK_STATUS = "ok"
INVALID_OR_MISSING_API_KEY_DETAIL = "Invalid or missing API key."
INVALID_OR_MISSING_BEARER_TOKEN_DETAIL = "Invalid or missing bearer token."
RATE_LIMIT_EXCEEDED_DETAIL = "Rate limit exceeded. Please retry later."
MODEL_UNAVAILABLE_DETAIL_PREFIX = "Model is unavailable"
UNSUPPORTED_TARGET_LANGUAGE_DETAIL_TEMPLATE = "Unsupported target_language '{alias}'. Supported: {supported}"
UNSUPPORTED_SOURCE_LANGUAGE_DETAIL_TEMPLATE = "Unsupported source_language '{alias}'. Supported: {supported}"
LANGUAGE_DETECTION_FAILED_DETAIL = "Could not detect source language. Please specify source_language explicitly."
HTTP_STATUS_UNSUPPORTED_TARGET_LANGUAGE = 422
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_MODEL_UNAVAILABLE = 503
HTTP_STATUS_TOO_MANY_REQUESTS = 429
UNAUTHORIZED_RESPONSE_DESCRIPTION = "Невалідні або відсутні облікові дані авторизації."
MODEL_UNAVAILABLE_RESPONSE_DESCRIPTION = "Модель недоступна або не ініціалізувалась."
RATE_LIMIT_RESPONSE_DESCRIPTION = "Перевищено ліміт запитів."
TRANSLATE_SUMMARY = "Переклад тексту у підтримувану мову"
TRANSLATE_DESCRIPTION = (
    "Виконує переклад одного тексту (наприклад, арабського `arb_Arab`) "
    "у підтримувану цільову мову."
)
LANGUAGES_SUMMARY = "Підтримувані мови"
LANGUAGES_DESCRIPTION = "Повертає підтримувані alias-и і відповідні NLLB-коди."
ROOT_ENDPOINT_PATH = "/"
ROOT_SUMMARY = "Опис API"
ROOT_DESCRIPTION = "Повертає JSON-опис сервісу та посилання на документацію Swagger UI."
TEXT_MIN_LENGTH = 1

SUPPORTED_TARGET_LANGUAGES = {
    "ru": "rus_Cyrl",
    "uk": "ukr_Cyrl",
}
SUPPORTED_SOURCE_LANGUAGES: dict[str, str] = {
    # Короткі alias-и для зворотної сумісності
    "ar": "arb_Arab",
    "en": "eng_Latn",
    "pl": "pol_Latn",
    "sk": "slk_Latn",
    "hu": "hun_Latn",
    "ro": "ron_Latn",
    "md": "ron_Latn",  # Moldova (Romanian)
    "be": "bel_Cyrl",
    "ru": "rus_Cyrl",
    # Усі 200 мов NLLB-200 (alias = NLLB-код)
    "ace_Arab": "ace_Arab",  # Acehnese (Arabic script)
    "ace_Latn": "ace_Latn",  # Acehnese (Latin script)
    "acm_Arab": "acm_Arab",  # Mesopotamian Arabic
    "acq_Arab": "acq_Arab",  # Ta'izzi-Adeni Arabic
    "aeb_Arab": "aeb_Arab",  # Tunisian Arabic
    "afr_Latn": "afr_Latn",  # Afrikaans
    "ajp_Arab": "ajp_Arab",  # South Levantine Arabic
    "aka_Latn": "aka_Latn",  # Akan
    "amh_Ethi": "amh_Ethi",  # Amharic
    "apc_Arab": "apc_Arab",  # North Levantine Arabic
    "arb_Arab": "arb_Arab",  # Modern Standard Arabic
    "ars_Arab": "ars_Arab",  # Najdi Arabic
    "ary_Arab": "ary_Arab",  # Moroccan Arabic
    "arz_Arab": "arz_Arab",  # Egyptian Arabic
    "asm_Beng": "asm_Beng",  # Assamese
    "ast_Latn": "ast_Latn",  # Asturian
    "awa_Deva": "awa_Deva",  # Awadhi
    "ayr_Latn": "ayr_Latn",  # Central Aymara
    "azb_Arab": "azb_Arab",  # South Azerbaijani
    "azj_Latn": "azj_Latn",  # North Azerbaijani
    "bak_Cyrl": "bak_Cyrl",  # Bashkir
    "bam_Latn": "bam_Latn",  # Bambara
    "ban_Latn": "ban_Latn",  # Balinese
    "bel_Cyrl": "bel_Cyrl",  # Belarusian
    "bem_Latn": "bem_Latn",  # Bemba
    "ben_Beng": "ben_Beng",  # Bengali
    "bho_Deva": "bho_Deva",  # Bhojpuri
    "bjn_Arab": "bjn_Arab",  # Banjar (Arabic script)
    "bjn_Latn": "bjn_Latn",  # Banjar (Latin script)
    "bod_Tibt": "bod_Tibt",  # Standard Tibetan
    "bos_Latn": "bos_Latn",  # Bosnian
    "bug_Latn": "bug_Latn",  # Buginese
    "bul_Cyrl": "bul_Cyrl",  # Bulgarian
    "cat_Latn": "cat_Latn",  # Catalan
    "ceb_Latn": "ceb_Latn",  # Cebuano
    "ces_Latn": "ces_Latn",  # Czech
    "cjk_Latn": "cjk_Latn",  # Chokwe
    "ckb_Arab": "ckb_Arab",  # Central Kurdish
    "crh_Latn": "crh_Latn",  # Crimean Tatar
    "cym_Latn": "cym_Latn",  # Welsh
    "dan_Latn": "dan_Latn",  # Danish
    "deu_Latn": "deu_Latn",  # German
    "dik_Latn": "dik_Latn",  # Southwestern Dinka
    "dyu_Latn": "dyu_Latn",  # Dyula
    "dzo_Tibt": "dzo_Tibt",  # Dzongkha
    "ell_Grek": "ell_Grek",  # Greek
    "eng_Latn": "eng_Latn",  # English
    "epo_Latn": "epo_Latn",  # Esperanto
    "est_Latn": "est_Latn",  # Estonian
    "eus_Latn": "eus_Latn",  # Basque
    "ewe_Latn": "ewe_Latn",  # Ewe
    "fao_Latn": "fao_Latn",  # Faroese
    "fij_Latn": "fij_Latn",  # Fijian
    "fin_Latn": "fin_Latn",  # Finnish
    "fon_Latn": "fon_Latn",  # Fon
    "fra_Latn": "fra_Latn",  # French
    "fur_Latn": "fur_Latn",  # Friulian
    "fuv_Latn": "fuv_Latn",  # Nigerian Fulfulde
    "gaz_Latn": "gaz_Latn",  # West Central Oromo
    "gla_Latn": "gla_Latn",  # Scottish Gaelic
    "gle_Latn": "gle_Latn",  # Irish
    "glg_Latn": "glg_Latn",  # Galician
    "grn_Latn": "grn_Latn",  # Guarani
    "guj_Gujr": "guj_Gujr",  # Gujarati
    "hat_Latn": "hat_Latn",  # Haitian Creole
    "hau_Latn": "hau_Latn",  # Hausa
    "heb_Hebr": "heb_Hebr",  # Hebrew
    "hin_Deva": "hin_Deva",  # Hindi
    "hne_Deva": "hne_Deva",  # Chhattisgarhi
    "hrv_Latn": "hrv_Latn",  # Croatian
    "hun_Latn": "hun_Latn",  # Hungarian
    "hye_Armn": "hye_Armn",  # Armenian
    "ibo_Latn": "ibo_Latn",  # Igbo
    "ilo_Latn": "ilo_Latn",  # Ilocano
    "ind_Latn": "ind_Latn",  # Indonesian
    "isl_Latn": "isl_Latn",  # Icelandic
    "ita_Latn": "ita_Latn",  # Italian
    "jav_Latn": "jav_Latn",  # Javanese
    "jpn_Jpan": "jpn_Jpan",  # Japanese
    "kab_Latn": "kab_Latn",  # Kabyle
    "kac_Latn": "kac_Latn",  # Jingpho
    "kam_Latn": "kam_Latn",  # Kamba
    "kan_Knda": "kan_Knda",  # Kannada
    "kas_Arab": "kas_Arab",  # Kashmiri (Arabic script)
    "kas_Deva": "kas_Deva",  # Kashmiri (Devanagari script)
    "kat_Geor": "kat_Geor",  # Georgian
    "kaz_Cyrl": "kaz_Cyrl",  # Kazakh
    "kbp_Latn": "kbp_Latn",  # Kabiyè
    "kea_Latn": "kea_Latn",  # Kabuverdianu
    "khk_Cyrl": "khk_Cyrl",  # Halh Mongolian
    "khm_Khmr": "khm_Khmr",  # Khmer
    "kik_Latn": "kik_Latn",  # Kikuyu
    "kin_Latn": "kin_Latn",  # Kinyarwanda
    "kir_Cyrl": "kir_Cyrl",  # Kyrgyz
    "kmb_Latn": "kmb_Latn",  # Kimbundu
    "kmr_Latn": "kmr_Latn",  # Northern Kurdish
    "knc_Arab": "knc_Arab",  # Central Kanuri (Arabic script)
    "knc_Latn": "knc_Latn",  # Central Kanuri (Latin script)
    "kon_Latn": "kon_Latn",  # Kikongo
    "kor_Hang": "kor_Hang",  # Korean
    "lao_Laoo": "lao_Laoo",  # Lao
    "lij_Latn": "lij_Latn",  # Ligurian
    "lim_Latn": "lim_Latn",  # Limburgish
    "lin_Latn": "lin_Latn",  # Lingala
    "lit_Latn": "lit_Latn",  # Lithuanian
    "lmo_Latn": "lmo_Latn",  # Lombard
    "ltg_Latn": "ltg_Latn",  # Latgalian
    "ltz_Latn": "ltz_Latn",  # Luxembourgish
    "lua_Latn": "lua_Latn",  # Luba-Kasai
    "lug_Latn": "lug_Latn",  # Ganda
    "luo_Latn": "luo_Latn",  # Luo
    "lus_Latn": "lus_Latn",  # Mizo
    "lvs_Latn": "lvs_Latn",  # Standard Latvian
    "mag_Deva": "mag_Deva",  # Magahi
    "mai_Deva": "mai_Deva",  # Maithili
    "mal_Mlym": "mal_Mlym",  # Malayalam
    "mar_Deva": "mar_Deva",  # Marathi
    "min_Arab": "min_Arab",  # Minangkabau (Arabic script)
    "min_Latn": "min_Latn",  # Minangkabau (Latin script)
    "mkd_Cyrl": "mkd_Cyrl",  # Macedonian
    "mlt_Latn": "mlt_Latn",  # Maltese
    "mni_Beng": "mni_Beng",  # Meitei (Bengali script)
    "mos_Latn": "mos_Latn",  # Mossi
    "mri_Latn": "mri_Latn",  # Maori
    "mya_Mymr": "mya_Mymr",  # Burmese
    "nld_Latn": "nld_Latn",  # Dutch
    "nno_Latn": "nno_Latn",  # Norwegian Nynorsk
    "nob_Latn": "nob_Latn",  # Norwegian Bokmål
    "npi_Deva": "npi_Deva",  # Nepali
    "nso_Latn": "nso_Latn",  # Northern Sotho
    "nus_Latn": "nus_Latn",  # Nuer
    "nya_Latn": "nya_Latn",  # Nyanja
    "oci_Latn": "oci_Latn",  # Occitan
    "ory_Orya": "ory_Orya",  # Odia
    "pag_Latn": "pag_Latn",  # Pangasinan
    "pan_Guru": "pan_Guru",  # Eastern Panjabi
    "pap_Latn": "pap_Latn",  # Papiamento
    "pbt_Arab": "pbt_Arab",  # Southern Pashto
    "pes_Arab": "pes_Arab",  # Western Persian
    "plt_Latn": "plt_Latn",  # Plateau Malagasy
    "pol_Latn": "pol_Latn",  # Polish
    "por_Latn": "por_Latn",  # Portuguese
    "prs_Arab": "prs_Arab",  # Dari
    "quy_Latn": "quy_Latn",  # Ayacucho Quechua
    "ron_Latn": "ron_Latn",  # Romanian
    "run_Latn": "run_Latn",  # Rundi
    "rus_Cyrl": "rus_Cyrl",  # Russian
    "sag_Latn": "sag_Latn",  # Sango
    "san_Deva": "san_Deva",  # Sanskrit
    "sat_Olck": "sat_Olck",  # Santali
    "scn_Latn": "scn_Latn",  # Sicilian
    "shn_Mymr": "shn_Mymr",  # Shan
    "sin_Sinh": "sin_Sinh",  # Sinhala
    "slk_Latn": "slk_Latn",  # Slovak
    "slv_Latn": "slv_Latn",  # Slovenian
    "smo_Latn": "smo_Latn",  # Samoan
    "sna_Latn": "sna_Latn",  # Shona
    "snd_Arab": "snd_Arab",  # Sindhi
    "som_Latn": "som_Latn",  # Somali
    "sot_Latn": "sot_Latn",  # Southern Sotho
    "spa_Latn": "spa_Latn",  # Spanish
    "srd_Latn": "srd_Latn",  # Sardinian
    "srp_Cyrl": "srp_Cyrl",  # Serbian
    "ssw_Latn": "ssw_Latn",  # Swati
    "sun_Latn": "sun_Latn",  # Sundanese
    "swe_Latn": "swe_Latn",  # Swedish
    "swh_Latn": "swh_Latn",  # Swahili
    "szl_Latn": "szl_Latn",  # Silesian
    "tam_Taml": "tam_Taml",  # Tamil
    "taq_Latn": "taq_Latn",  # Tamasheq (Latin script)
    "taq_Tfng": "taq_Tfng",  # Tamasheq (Tifinagh script)
    "tat_Cyrl": "tat_Cyrl",  # Tatar
    "tel_Telu": "tel_Telu",  # Telugu
    "tgk_Cyrl": "tgk_Cyrl",  # Tajik
    "tgl_Latn": "tgl_Latn",  # Tagalog
    "tha_Thai": "tha_Thai",  # Thai
    "tir_Ethi": "tir_Ethi",  # Tigrinya
    "tpi_Latn": "tpi_Latn",  # Tok Pisin
    "tsn_Latn": "tsn_Latn",  # Tswana
    "tso_Latn": "tso_Latn",  # Tsonga
    "tuk_Latn": "tuk_Latn",  # Turkmen
    "tum_Latn": "tum_Latn",  # Tumbuka
    "tur_Latn": "tur_Latn",  # Turkish
    "twi_Latn": "twi_Latn",  # Twi
    "tzm_Tfng": "tzm_Tfng",  # Central Atlas Tamazight
    "uig_Arab": "uig_Arab",  # Uyghur
    "ukr_Cyrl": "ukr_Cyrl",  # Ukrainian
    "umb_Latn": "umb_Latn",  # Umbundu
    "urd_Arab": "urd_Arab",  # Urdu
    "uzn_Latn": "uzn_Latn",  # Northern Uzbek
    "vec_Latn": "vec_Latn",  # Venetian
    "vie_Latn": "vie_Latn",  # Vietnamese
    "war_Latn": "war_Latn",  # Waray
    "wol_Latn": "wol_Latn",  # Wolof
    "xho_Latn": "xho_Latn",  # Xhosa
    "ydd_Hebr": "ydd_Hebr",  # Eastern Yiddish
    "yor_Latn": "yor_Latn",  # Yoruba
    "yue_Hant": "yue_Hant",  # Yue Chinese
    "zho_Hans": "zho_Hans",  # Chinese (Simplified)
    "zho_Hant": "zho_Hant",  # Chinese (Traditional)
    "zsm_Latn": "zsm_Latn",  # Standard Malay
    "zul_Latn": "zul_Latn",  # Zulu
}


class Settings(BaseSettings):
    """Конфігурація сервісу перекладу, що читається з env."""

    model_config = SettingsConfigDict(env_prefix="NLLB_", env_file=".env", extra="ignore")

    model_name: str = "facebook/nllb-200-1.3B"
    tgt_lang: str = "rus_Cyrl"
    default_target_language: str = "ru"
    api_key_enabled: bool = False
    api_key: str | None = None
    bearer_token_enabled: bool = False
    bearer_token: str | None = None
    model_cache_dir: str = "/app/storage/huggingface"
    transformers_offline: bool = False
    max_length: int = 1024
    request_text_max_length: int = 10_000
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    ct2_model_dir: str = "/app/storage/ct2-nllb-1.3b-nondistilled-int8"
    ct2_device: str = "cpu"
    ct2_inter_threads: int = 1

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

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str | None) -> str | None:
        """Перевіряє формат API ключа доступу.

        Args:
            value: Значення API-ключа з env.

        Returns:
            Обрізане значення ключа або None.
        """
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @field_validator("bearer_token")
    @classmethod
    def validate_bearer_token(cls, value: str | None) -> str | None:
        """Перевіряє формат bearer токена доступу.

        Args:
            value: Значення bearer-токена з env.

        Returns:
            Обрізане значення токена або None.
        """
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @model_validator(mode="after")
    def validate_auth_settings(self) -> "Settings":
        """Перевіряє узгодженість auth-настройок."""
        if self.api_key_enabled and not self.api_key:
            raise ValueError("NLLB_API_KEY must be set when NLLB_API_KEY_ENABLED=true.")
        if self.bearer_token_enabled and not self.bearer_token:
            raise ValueError("NLLB_BEARER_TOKEN must be set when NLLB_BEARER_TOKEN_ENABLED=true.")
        return self

    @field_validator("max_length")
    @classmethod
    def validate_max_length(cls, value: int) -> int:
        """Перевіряє обмеження довжини генерації перекладу.

        Args:
            value: Значення `NLLB_MAX_LENGTH` з env.

        Returns:
            Ціле невід'ємне значення довжини.

        Raises:
            ValueError: Якщо значення від'ємне.
        """
        if value < 0:
            raise ValueError("NLLB_MAX_LENGTH must be greater than or equal to 0.")
        return value

    @field_validator("model_cache_dir")
    @classmethod
    def validate_model_cache_dir(cls, value: str) -> str:
        """Перевіряє директорію локального кешу моделі.

        Args:
            value: Шлях до директорії кешу з env.

        Returns:
            Нормалізований непорожній шлях.

        Raises:
            ValueError: Якщо шлях порожній.
        """
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("NLLB_MODEL_CACHE_DIR must not be empty.")
        return normalized_value

    @field_validator("request_text_max_length")
    @classmethod
    def validate_request_text_max_length(cls, value: int) -> int:
        """Перевіряє ліміт довжини вхідного тексту для API.

        Args:
            value: Значення `NLLB_REQUEST_TEXT_MAX_LENGTH` з env.

        Returns:
            Додатне ціле значення.

        Raises:
            ValueError: Якщо значення менше 1.
        """
        if value < TEXT_MIN_LENGTH:
            raise ValueError("NLLB_REQUEST_TEXT_MAX_LENGTH must be greater than or equal to 1.")
        return value

    @field_validator("rate_limit_requests")
    @classmethod
    def validate_rate_limit_requests(cls, value: int) -> int:
        """Перевіряє ліміт кількості запитів у вікні rate limit."""
        if value < 1:
            raise ValueError("NLLB_RATE_LIMIT_REQUESTS must be greater than or equal to 1.")
        return value

    @field_validator("rate_limit_window_seconds")
    @classmethod
    def validate_rate_limit_window_seconds(cls, value: int) -> int:
        """Перевіряє тривалість вікна rate limit у секундах."""
        if value < 1:
            raise ValueError("NLLB_RATE_LIMIT_WINDOW_SECONDS must be greater than or equal to 1.")
        return value

    @field_validator("ct2_device")
    @classmethod
    def validate_ct2_device(cls, value: str) -> str:
        """Перевіряє допустимий пристрій для CTranslate2."""
        normalized = value.strip().lower()
        if normalized not in {"cpu", "cuda"}:
            raise ValueError("NLLB_CT2_DEVICE must be 'cpu' or 'cuda'.")
        return normalized

    @field_validator("ct2_inter_threads")
    @classmethod
    def validate_ct2_inter_threads(cls, value: int) -> int:
        """Перевіряє кількість паралельних потоків для CTranslate2."""
        if value < 1:
            raise ValueError("NLLB_CT2_INTER_THREADS must be greater than or equal to 1.")
        return value


settings = Settings()
