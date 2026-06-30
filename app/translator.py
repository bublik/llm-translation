import re
from pathlib import Path

from app.config import settings

_DEFAULT_MAX_DECODING_LENGTH = 1024

# Понад цей поріг вхід розбивається на речення для уникнення attention degradation.
# 256 — рекомендований ліміт для NLLB-200 (офіційний контекст 512 токенів).
_MAX_SOURCE_TOKENS = 256

# Розбивка на речення: крапка/! /? /؟/۔/। з пробілом після
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟۔।])\s+")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


class NLLBTranslator:
    """Обгортка над CTranslate2 NLLB-моделлю для перекладу тексту."""

    def __init__(self) -> None:
        import ctranslate2
        from transformers import AutoTokenizer

        ct2_model_dir = Path(settings.ct2_model_dir)
        if not ct2_model_dir.exists():
            raise RuntimeError(
                f"CTranslate2 model not found at '{ct2_model_dir}'. "
                "Run scripts/convert_model.py first."
            )

        self._ct2 = ctranslate2.Translator(
            str(ct2_model_dir),
            device=settings.ct2_device,
            inter_threads=settings.ct2_inter_threads,
        )

        cache_dir = Path(settings.model_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._tokenizer = AutoTokenizer.from_pretrained(
            settings.model_name,
            cache_dir=str(cache_dir),
            local_files_only=settings.transformers_offline,
        )

    def translate(self, text: str, target_language: str, source_language: str) -> str:
        self._tokenizer.src_lang = source_language
        encoded = self._tokenizer(text)

        if len(encoded["input_ids"]) <= _MAX_SOURCE_TOKENS:
            return self._decode(self._run(encoded, target_language))

        sentences = _split_sentences(text)
        if len(sentences) <= 1:
            return self._decode(self._run(encoded, target_language))

        parts: list[str] = []
        for sentence in sentences:
            self._tokenizer.src_lang = source_language
            sent_encoded = self._tokenizer(sentence)
            parts.append(self._decode(self._run(sent_encoded, target_language)))
        return " ".join(parts)

    def _run(self, encoded: dict, target_language: str) -> list[str]:
        source_tokens = self._tokenizer.convert_ids_to_tokens(encoded["input_ids"])
        max_decoding_length = settings.max_length if settings.max_length > 0 else _DEFAULT_MAX_DECODING_LENGTH
        results = self._ct2.translate_batch(
            [source_tokens],
            target_prefix=[[target_language]],
            max_decoding_length=max_decoding_length,
        )
        return results[0].hypotheses[0][1:]

    def _decode(self, tokens: list[str]) -> str:
        ids = self._tokenizer.convert_tokens_to_ids(tokens)
        return self._tokenizer.decode(ids, skip_special_tokens=True)


# Відображення NLLB-кодів на людські назви мов для промпту EuroLLM
_NLLB_TO_LANG_NAME: dict[str, str] = {
    "afr_Latn": "Afrikaans",
    "amh_Ethi": "Amharic",
    "arb_Arab": "Arabic",
    "ary_Arab": "Moroccan Arabic",
    "arz_Arab": "Egyptian Arabic",
    "acm_Arab": "Mesopotamian Arabic",
    "acq_Arab": "Yemeni Arabic",
    "aeb_Arab": "Tunisian Arabic",
    "ajp_Arab": "South Levantine Arabic",
    "apc_Arab": "North Levantine Arabic",
    "ars_Arab": "Najdi Arabic",
    "azj_Latn": "Azerbaijani",
    "bel_Cyrl": "Belarusian",
    "ben_Beng": "Bengali",
    "bos_Latn": "Bosnian",
    "bul_Cyrl": "Bulgarian",
    "cat_Latn": "Catalan",
    "ces_Latn": "Czech",
    "cym_Latn": "Welsh",
    "dan_Latn": "Danish",
    "deu_Latn": "German",
    "ell_Grek": "Greek",
    "eng_Latn": "English",
    "est_Latn": "Estonian",
    "eus_Latn": "Basque",
    "fin_Latn": "Finnish",
    "fra_Latn": "French",
    "glg_Latn": "Galician",
    "guj_Gujr": "Gujarati",
    "hau_Latn": "Hausa",
    "heb_Hebr": "Hebrew",
    "hin_Deva": "Hindi",
    "hrv_Latn": "Croatian",
    "hun_Latn": "Hungarian",
    "hye_Armn": "Armenian",
    "ibo_Latn": "Igbo",
    "ind_Latn": "Indonesian",
    "isl_Latn": "Icelandic",
    "ita_Latn": "Italian",
    "jpn_Jpan": "Japanese",
    "kan_Knda": "Kannada",
    "kat_Geor": "Georgian",
    "kaz_Cyrl": "Kazakh",
    "khm_Khmr": "Khmer",
    "kin_Latn": "Kinyarwanda",
    "kor_Hang": "Korean",
    "lit_Latn": "Lithuanian",
    "lvs_Latn": "Latvian",
    "mal_Mlym": "Malayalam",
    "mar_Deva": "Marathi",
    "mkd_Cyrl": "Macedonian",
    "mlt_Latn": "Maltese",
    "mya_Mymr": "Burmese",
    "nld_Latn": "Dutch",
    "nob_Latn": "Norwegian",
    "npi_Deva": "Nepali",
    "pes_Arab": "Persian",
    "pol_Latn": "Polish",
    "por_Latn": "Portuguese",
    "ron_Latn": "Romanian",
    "rus_Cyrl": "Russian",
    "sin_Sinh": "Sinhala",
    "slk_Latn": "Slovak",
    "slv_Latn": "Slovenian",
    "som_Latn": "Somali",
    "spa_Latn": "Spanish",
    "srp_Cyrl": "Serbian",
    "swe_Latn": "Swedish",
    "swh_Latn": "Swahili",
    "tam_Taml": "Tamil",
    "tel_Telu": "Telugu",
    "tgl_Latn": "Tagalog",
    "tha_Thai": "Thai",
    "tur_Latn": "Turkish",
    "ukr_Cyrl": "Ukrainian",
    "urd_Arab": "Urdu",
    "uzn_Latn": "Uzbek",
    "vie_Latn": "Vietnamese",
    "yor_Latn": "Yoruba",
    "yue_Hant": "Cantonese",
    "zho_Hans": "Chinese",
    "zho_Hant": "Chinese (Traditional)",
    "zul_Latn": "Zulu",
}

class EuroLLMTranslator:
    """Перекладач на базі EuroLLM через llama-cpp-python (ChatML, CPU inference).

    Використовує офіційний формат перекладу EuroLLM (порожній system + мітки
    мов `English: ... Ukrainian:`) і перекладає вхід порядково. Порядкове
    розбиття критичне: на довгому шумному блоці модель «вискакує» з режиму
    перекладу й лишає речення мовою оригіналу; короткі рядки тримають її в
    режимі перекладу (частка неперекладеного падає з ~90% до ~15%).
    """

    def __init__(self) -> None:
        from llama_cpp import Llama

        model_path = Path(settings.eurollm_model_path)
        if not model_path.exists():
            raise RuntimeError(
                f"EuroLLM model not found at '{model_path}'. "
                "Download the GGUF file first."
            )

        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=settings.eurollm_n_ctx,
            n_threads=settings.eurollm_n_threads,
            verbose=False,
        )

    def translate(self, text: str, target_language: str, source_language: str) -> str:
        src = _NLLB_TO_LANG_NAME.get(source_language, source_language)
        tgt = _NLLB_TO_LANG_NAME.get(target_language, target_language)

        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) <= 1:
            return self._run(text.strip(), src, tgt)
        return "\n".join(self._run(line.strip(), src, tgt) for line in lines)

    def _run(self, text: str, src: str, tgt: str) -> str:
        # Офіційний формат EuroLLM: порожній system, мітки мов, перекладач
        # продовжує після "{tgt}: ".
        prompt = (
            f"<|im_start|>system\n<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Translate the following {src} source text to {tgt}:\n"
            f"{src}: {text}\n{tgt}: <|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        result = self._llm(
            prompt,
            max_tokens=settings.eurollm_max_tokens,
            temperature=0.0,
            repeat_penalty=settings.eurollm_repeat_penalty,
            stop=["<|im_end|>", "<|im_start|>"],
        )
        return result["choices"][0]["text"].strip()


def create_translator() -> "NLLBTranslator | EuroLLMTranslator":
    """Створює транслятор згідно налаштування NLLB_TRANSLATION_BACKEND."""
    backend = settings.translation_backend.lower()
    if backend == "eurollm":
        return EuroLLMTranslator()
    return NLLBTranslator()
