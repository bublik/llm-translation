import re
from pathlib import Path

import ctranslate2
from transformers import AutoTokenizer

from app.config import settings

_DEFAULT_MAX_DECODING_LENGTH = 1024

# Понад цей поріг входу NLLB починає "забувати" початок тексту.
# Відповідає приблизно 3-4 середнім реченням арабського тексту.
_MAX_SOURCE_TOKENS = 100

# Розбивка на речення: крапка/! /? /؟/۔/। з пробілом після
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟۔।])\s+")


def _split_sentences(text: str) -> list[str]:
    """Розбиває текст на речення за знаками пунктуації."""
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


class NLLBTranslator:
    """Обгортка над CTranslate2 NLLB-моделлю для перекладу тексту."""

    def __init__(self) -> None:
        """Ініціалізує CTranslate2 Translator і токенайзер із локального кешу."""
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
        """Перекладає вхідний текст у вказану цільову мову NLLB.

        Якщо текст довший за _MAX_SOURCE_TOKENS, автоматично розбивається
        на речення і перекладається частинами, щоб уникнути attention degradation.

        Args:
            text: Вхідний текст для перекладу.
            target_language: Код цільової мови NLLB (наприклад, `rus_Cyrl`).
            source_language: Код вхідної мови NLLB (наприклад, `arb_Arab`).

        Returns:
            Перекладений текст.
        """
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
        """Запускає CT2-інференс і повертає передбачені токени (без мовного префіксу)."""
        source_tokens = self._tokenizer.convert_ids_to_tokens(encoded["input_ids"])
        max_decoding_length = settings.max_length if settings.max_length > 0 else _DEFAULT_MAX_DECODING_LENGTH
        results = self._ct2.translate_batch(
            [source_tokens],
            target_prefix=[[target_language]],
            max_decoding_length=max_decoding_length,
        )
        return results[0].hypotheses[0][1:]

    def _decode(self, tokens: list[str]) -> str:
        """Конвертує CT2-токени у рядок через токенайзер."""
        ids = self._tokenizer.convert_tokens_to_ids(tokens)
        return self._tokenizer.decode(ids, skip_special_tokens=True)
